"""
DDR Intelligence Engine - Flask Web UI

Live demo interface for generating Defect Diagnostic Reports (DDRs).
Users upload two PDFs, click Generate, and download the DDR report.

Routes:
- GET / — HTML upload page
- POST /generate — Start pipeline job
- GET /status/<job_id> — Poll job status
- GET /download/<job_id> — Download generated PDF
"""

import logging
import os
import shutil
import threading
import traceback
import uuid
from datetime import datetime
from pathlib import Path
from tempfile import mkdtemp

from flask import Flask, jsonify, render_template_string, request, send_file

# Configure logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Flask app
app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024  # 100 MB max upload

# In-memory job status tracking
# {job_id: {"status": "running"/"done"/"error", "message": str, "progress": int, "pdf_path": str or None, "error": str or None}}
job_status = {}

# ============================================================================
# HTML TEMPLATE FOR UPLOAD PAGE
# ============================================================================

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>DDR Intelligence Engine</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
            background: #f8f9fa;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
            color: #2c3e50;
        }

        .container {
            max-width: 680px;
            width: 100%;
        }

        .card {
            background: #ffffff;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
            padding: 40px 30px;
        }

        .header {
            text-align: center;
            margin-bottom: 30px;
        }

        .header h1 {
            font-size: 28px;
            font-weight: 700;
            color: #2c3e50;
            margin-bottom: 8px;
        }

        .header p {
            font-size: 14px;
            color: #7f8c8d;
            line-height: 1.5;
        }

        .upload-section {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin-bottom: 30px;
        }

        .upload-group {
            display: flex;
            flex-direction: column;
        }

        .upload-group label {
            font-size: 12px;
            font-weight: 600;
            color: #2c3e50;
            margin-bottom: 8px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        .file-input-wrapper {
            position: relative;
            overflow: hidden;
        }

        .file-input-wrapper input[type="file"] {
            position: absolute;
            left: -9999px;
        }

        .file-input-label {
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
            border: 2px dashed #e0e0e0;
            border-radius: 6px;
            cursor: pointer;
            background: #f9f9f9;
            transition: all 0.2s ease;
            font-size: 13px;
            color: #7f8c8d;
            text-align: center;
            min-height: 80px;
        }

        .file-input-wrapper input[type="file"]:hover + .file-input-label {
            border-color: #c0392b;
            background: #fff5f4;
        }

        .file-input-wrapper input[type="file"]:focus + .file-input-label {
            border-color: #c0392b;
            outline: none;
        }

        .file-name {
            font-size: 12px;
            color: #c0392b;
            margin-top: 4px;
            font-weight: 500;
        }

        .button-group {
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
        }

        .btn {
            flex: 1;
            padding: 14px 24px;
            border: none;
            border-radius: 6px;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s ease;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        .btn-primary {
            background: #c0392b;
            color: white;
        }

        .btn-primary:hover:not(:disabled) {
            background: #a93226;
            box-shadow: 0 4px 12px rgba(192, 57, 43, 0.2);
        }

        .btn-primary:disabled {
            background: #bdc3c7;
            cursor: not-allowed;
            opacity: 0.7;
        }

        .btn-success {
            background: #27ae60;
            color: white;
        }

        .btn-success:hover {
            background: #229954;
        }

        .status-container {
            display: none;
            padding: 20px;
            background: #f9f9f9;
            border-radius: 6px;
            border-left: 4px solid #c0392b;
            margin-bottom: 20px;
        }

        .status-container.show {
            display: block;
        }

        .spinner {
            display: inline-block;
            width: 16px;
            height: 16px;
            border: 3px solid #e0e0e0;
            border-top-color: #c0392b;
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
            margin-right: 8px;
            vertical-align: middle;
        }

        @keyframes spin {
            to { transform: rotate(360deg); }
        }

        .status-message {
            display: flex;
            align-items: center;
            font-size: 14px;
            color: #2c3e50;
            margin-bottom: 12px;
        }

        .progress-bar {
            width: 100%;
            height: 6px;
            background: #e0e0e0;
            border-radius: 3px;
            overflow: hidden;
            margin-bottom: 8px;
        }

        .progress-fill {
            height: 100%;
            background: #c0392b;
            transition: width 0.3s ease;
            width: 0%;
        }

        .progress-text {
            font-size: 12px;
            color: #7f8c8d;
            text-align: right;
        }

        .error-message {
            padding: 12px;
            background: #fadbd8;
            border-left: 4px solid #c0392b;
            color: #a93226;
            border-radius: 4px;
            font-size: 13px;
            margin-bottom: 12px;
        }

        .success-message {
            padding: 12px;
            background: #d5f4e6;
            border-left: 4px solid #27ae60;
            color: #196f3d;
            border-radius: 4px;
            font-size: 13px;
            margin-bottom: 12px;
        }

        .download-link {
            display: inline-block;
            padding: 10px 16px;
            background: #27ae60;
            color: white;
            text-decoration: none;
            border-radius: 4px;
            font-size: 13px;
            font-weight: 600;
        }

        .download-link:hover {
            background: #229954;
        }

        @media (max-width: 600px) {
            .card {
                padding: 20px 15px;
            }

            .header h1 {
                font-size: 22px;
            }

            .upload-section {
                grid-template-columns: 1fr;
                gap: 15px;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="card">
            <div class="header">
                <h1>DDR Intelligence Engine</h1>
                <p>Upload inspection documents to generate a professional Defect Diagnostic Report</p>
            </div>

            <form id="uploadForm">
                <div class="upload-section">
                    <div class="upload-group">
                        <label for="inspectionPdf">Inspection Report (PDF)</label>
                        <div class="file-input-wrapper">
                            <input type="file" id="inspectionPdf" name="inspection_pdf" accept=".pdf" required>
                            <label for="inspectionPdf" class="file-input-label">
                                📄 Click to upload
                            </label>
                        </div>
                        <div class="file-name" id="inspectionFileName"></div>
                    </div>

                    <div class="upload-group">
                        <label for="thermalPdf">Thermal Report (PDF)</label>
                        <div class="file-input-wrapper">
                            <input type="file" id="thermalPdf" name="thermal_pdf" accept=".pdf" required>
                            <label for="thermalPdf" class="file-input-label">
                                📄 Click to upload
                            </label>
                        </div>
                        <div class="file-name" id="thermalFileName"></div>
                    </div>
                </div>

                <div class="button-group">
                    <button type="button" id="generateBtn" class="btn btn-primary">
                        🚀 Generate DDR Report
                    </button>
                </div>

                <div id="statusContainer" class="status-container">
                    <div class="status-message">
                        <span class="spinner"></span>
                        <span id="statusMessage">Processing...</span>
                    </div>
                    <div class="progress-bar">
                        <div class="progress-fill" id="progressFill" style="width: 0%"></div>
                    </div>
                    <div class="progress-text"><span id="progressPercent">0</span>%</div>
                </div>

                <div id="errorContainer"></div>
                <div id="successContainer"></div>
            </form>
        </div>
    </div>

    <script>
        // File input handling
        document.getElementById('inspectionPdf').addEventListener('change', function() {
            document.getElementById('inspectionFileName').textContent = this.files[0]?.name || '';
        });

        document.getElementById('thermalPdf').addEventListener('change', function() {
            document.getElementById('thermalFileName').textContent = this.files[0]?.name || '';
        });

        // Form submission
        document.getElementById('generateBtn').addEventListener('click', async function() {
            const inspectionFile = document.getElementById('inspectionPdf').files[0];
            const thermalFile = document.getElementById('thermalPdf').files[0];

            if (!inspectionFile || !thermalFile) {
                alert('Please select both inspection and thermal PDFs');
                return;
            }

            // Prepare form data
            const formData = new FormData();
            formData.append('inspection_pdf', inspectionFile);
            formData.append('thermal_pdf', thermalFile);

            // Show status, disable button
            document.getElementById('statusContainer').classList.add('show');
            document.getElementById('errorContainer').innerHTML = '';
            document.getElementById('successContainer').innerHTML = '';
            document.getElementById('generateBtn').disabled = true;

            try {
                // Start job
                const response = await fetch('/generate', {
                    method: 'POST',
                    body: formData
                });

                if (!response.ok) {
                    throw new Error('Failed to start job: ' + response.statusText);
                }

                const data = await response.json();
                const jobId = data.job_id;

                // Poll status
                pollStatus(jobId);
            } catch (error) {
                showError(error.message);
                document.getElementById('generateBtn').disabled = false;
            }
        });

        async function pollStatus(jobId) {
            const maxAttempts = 600; // 20 minutes (2s intervals)
            let attempts = 0;

            const poll = async () => {
                if (attempts >= maxAttempts) {
                    showError('Job timed out after 20 minutes');
                    document.getElementById('generateBtn').disabled = false;
                    return;
                }

                try {
                    const response = await fetch(`/status/${jobId}`);
                    if (!response.ok) {
                        throw new Error('Failed to fetch status');
                    }

                    const data = await response.json();
                    const { status, message, progress, pdf_path, error } = data;

                    // Update UI
                    document.getElementById('statusMessage').textContent = message || 'Processing...';
                    document.getElementById('progressFill').style.width = progress + '%';
                    document.getElementById('progressPercent').textContent = progress;

                    if (status === 'done') {
                        // Show download button
                        document.getElementById('statusContainer').classList.remove('show');
                        document.getElementById('successContainer').innerHTML = `
                            <div class="success-message">
                                ✓ Report generated successfully!
                                <br><br>
                                <a href="/download/${jobId}" class="download-link">⬇️ Download DDR Report</a>
                            </div>
                        `;
                        document.getElementById('generateBtn').disabled = false;
                    } else if (status === 'error') {
                        showError(error || message || 'Unknown error');
                        document.getElementById('statusContainer').classList.remove('show');
                        document.getElementById('generateBtn').disabled = false;
                    } else {
                        // Continue polling
                        attempts++;
                        setTimeout(poll, 2000);
                    }
                } catch (error) {
                    showError(error.message);
                    document.getElementById('statusContainer').classList.remove('show');
                    document.getElementById('generateBtn').disabled = false;
                }
            };

            poll();
        }

        function showError(message) {
            document.getElementById('errorContainer').innerHTML = `
                <div class="error-message">
                    ✗ ${message}
                </div>
            `;
        }
    </script>
</body>
</html>
"""


# ============================================================================
# ROUTE 1 — GET /
# ============================================================================


@app.route("/", methods=["GET"])
def index():
    """Render upload page."""
    return render_template_string(HTML_TEMPLATE)


# ============================================================================
# ROUTE 2 — POST /generate
# ============================================================================


def run_pipeline(job_id, inspection_path, thermal_path):
    """
    Background thread function to run the DDR pipeline.

    Updates job_status dict with progress at each step.

    Args:
        job_id: Unique job identifier
        inspection_path: Path to inspection PDF
        thermal_path: Path to thermal PDF
    """
    try:
        # Import here to avoid loading everything at startup
        from src.graph.workflow import compile_workflow

        logger.info(f"[{job_id}] Starting pipeline")

        # Update status: 10%
        job_status[job_id]["progress"] = 10
        job_status[job_id]["message"] = "Parsing inspection report..."
        logger.info(f"[{job_id}] {job_status[job_id]['message']}")

        # Compile workflow
        app_graph = compile_workflow()

        # Update status: 25%
        job_status[job_id]["progress"] = 25
        job_status[job_id]["message"] = "Extracting thermal data..."
        logger.info(f"[{job_id}] {job_status[job_id]['message']}")

        # Build initial state
        initial_state = {
            "inspection_pdf_path": str(inspection_path),
            "thermal_pdf_path": str(thermal_path),
            "iteration_count": 0,
            "agent_logs": [],
        }

        # Update status: 40%
        job_status[job_id]["progress"] = 40
        job_status[job_id]["message"] = "Building semantic graph..."
        logger.info(f"[{job_id}] {job_status[job_id]['message']}")

        # Run pipeline
        final_state = app_graph.invoke(initial_state)

        # Update status: 70%
        job_status[job_id]["progress"] = 70
        job_status[job_id]["message"] = "Retrieving treatment recommendations..."
        logger.info(f"[{job_id}] {job_status[job_id]['message']}")

        # Update status: 80%
        job_status[job_id]["progress"] = 80
        job_status[job_id]["message"] = "Validating report quality..."
        logger.info(f"[{job_id}] {job_status[job_id]['message']}")

        # Update status: 90%
        job_status[job_id]["progress"] = 90
        job_status[job_id]["message"] = "Generating PDF report..."
        logger.info(f"[{job_id}] {job_status[job_id]['message']}")

        # Extract report path (PDF preferred, fall back to HTML)
        pdf_path = final_state.get("final_ddr_pdf_path")
        html_path = final_state.get("final_ddr_html_path")
        
        logger.info(f"[{job_id}] Checking report paths...")
        logger.info(f"[{job_id}]   PDF path from state: {pdf_path}")
        logger.info(f"[{job_id}]   HTML path from state: {html_path}")
        if pdf_path:
            logger.info(f"[{job_id}]   PDF exists: {os.path.exists(pdf_path)}")
        if html_path:
            logger.info(f"[{job_id}]   HTML exists: {os.path.exists(html_path)}")
        
        report_path = None
        report_type = None

        if pdf_path and os.path.exists(pdf_path):
            report_path = pdf_path
            report_type = "PDF"
            logger.info(f"[{job_id}] Using PDF report: {report_path}")
        elif html_path and os.path.exists(html_path):
            report_path = html_path
            report_type = "HTML"
            logger.info(f"[{job_id}] Using HTML report: {report_path}")
            logger.warning(f"[{job_id}] PDF generation skipped (WeasyPrint unavailable). Using HTML report instead.")

        if not report_path:
            raise ValueError(f"Report generation failed - PDF path={pdf_path}, HTML path={html_path}. Neither file exists.")

        # Update status: 100%
        job_status[job_id]["progress"] = 100
        job_status[job_id]["message"] = "Complete"
        job_status[job_id]["status"] = "done"
        job_status[job_id]["pdf_path"] = report_path
        job_status[job_id]["report_type"] = report_type

        logger.info(f"[{job_id}] Pipeline complete. {report_type} report: {report_path}")

    except Exception as e:
        error_msg = str(e)
        logger.error(f"[{job_id}] Pipeline failed: {error_msg}")
        logger.error(f"[{job_id}] Traceback: {traceback.format_exc()}")

        job_status[job_id]["status"] = "error"
        job_status[job_id]["message"] = f"Error: {error_msg}"
        job_status[job_id]["error"] = error_msg


@app.route("/generate", methods=["POST"])
def generate():
    """
    Start a DDR generation job.

    Accepts multipart form with: inspection_pdf, thermal_pdf

    Returns: {"job_id": str}
    """
    if "inspection_pdf" not in request.files or "thermal_pdf" not in request.files:
        return jsonify({"error": "Missing PDF files"}), 400

    inspection_file = request.files["inspection_pdf"]
    thermal_file = request.files["thermal_pdf"]

    if not inspection_file.filename or not thermal_file.filename:
        return jsonify({"error": "No file selected"}), 400

    # Create job directory
    job_id = str(uuid.uuid4())
    job_dir = Path("/tmp/ddr_jobs") / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    # Save uploaded files
    inspection_path = job_dir / "inspection.pdf"
    thermal_path = job_dir / "thermal.pdf"

    inspection_file.save(inspection_path)
    thermal_file.save(thermal_path)

    logger.info(f"[{job_id}] Received files: {inspection_path.name}, {thermal_path.name}")

    # Initialize job status
    job_status[job_id] = {
        "status": "running",
        "message": "Initializing...",
        "progress": 0,
        "pdf_path": None,
        "error": None,
    }

    # Start background thread
    thread = threading.Thread(
        target=run_pipeline, args=(job_id, str(inspection_path), str(thermal_path))
    )
    thread.daemon = True
    thread.start()

    logger.info(f"[{job_id}] Job started")

    return jsonify({"job_id": job_id}), 202


# ============================================================================
# ROUTE 3 — GET /status/<job_id>
# ============================================================================


@app.route("/status/<job_id>", methods=["GET"])
def status(job_id):
    """
    Get job status.

    Returns: {"status": "running"|"done"|"error", "message": str, "progress": int, ...}
    """
    if job_id not in job_status:
        return (
            jsonify({"status": "error", "message": "Job not found", "progress": 0}),
            404,
        )

    return jsonify(job_status[job_id]), 200


# ============================================================================
# ROUTE 4 — GET /download/<job_id>
# ============================================================================


@app.route("/download/<job_id>", methods=["GET"])
def download(job_id):
    """
    Download generated DDR report (PDF or HTML).

    Returns: file or 404
    """
    if job_id not in job_status:
        return "Job not found", 404

    report_path = job_status[job_id].get("pdf_path")

    if not report_path or not os.path.exists(report_path):
        return "Report not found", 404

    # Detect file type
    is_pdf = report_path.lower().endswith(".pdf")
    is_html = report_path.lower().endswith(".html")

    if is_pdf:
        mimetype = "application/pdf"
        filename = "DDR_Report.pdf"
    elif is_html:
        mimetype = "text/html"
        filename = "DDR_Report.html"
    else:
        return "Unsupported file type", 400

    logger.info(f"[{job_id}] Downloading {report_path} ({filename})")

    return send_file(
        report_path,
        as_attachment=True,
        download_name=filename,
        mimetype=mimetype,
    )


# ============================================================================
# Error handlers
# ============================================================================


@app.errorhandler(413)
def file_too_large(error):
    """Handle file size limit exceeded."""
    return jsonify({"error": "File too large. Maximum size is 100 MB."}), 413


@app.errorhandler(500)
def internal_error(error):
    """Handle internal server errors."""
    logger.error(f"Internal server error: {error}")
    return jsonify({"error": "Internal server error"}), 500


# ============================================================================
# Main
# ============================================================================


if __name__ == "__main__":
    logger.info("Starting DDR Intelligence Engine web server")
    logger.info("Open http://localhost:5000 in your browser")

    app.run(debug=False, host="0.0.0.0", port=5000)
