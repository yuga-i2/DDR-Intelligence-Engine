QUICKSTART — DDR Intelligence Engine Live Demo
═════════════════════════════════════════════════════

WINDOWS (PowerShell)
────────────────────
1. Open PowerShell in the project folder

2. Run the demo script:
  .\run_demo.ps1 

   OR if you get a permissions error, run:
   powershell -ExecutionPolicy Bypass -File .\run_demo.ps1

3. Open http://localhost:5000 in your browser

4. Upload both PDFs and click "Generate DDR Report"


MACOS / LINUX (Bash)
─────────────────────
1. Open Terminal in the project folder

2. Run the demo script:
   bash run_demo.sh

3. Open http://localhost:5000 in your browser

4. Upload both PDFs and click "Generate DDR Report"


MANUAL SETUP (All Platforms)
─────────────────────────────
If the auto scripts don't work:

1. Install Flask:
   pip install flask

2. Create .env file (if it doesn't exist):
   copy .env.example .env
   
   Then edit .env and add your GROQ_API_KEY
   (Get free key at https://console.groq.com)

3. Start the server:
   python app.py

4. Open http://localhost:5000 in your browser


COMMAND LINE (CLI)
──────────────────
Instead of the web UI, you can use the command line:

python main.py --inspection data/Sample_Report.pdf --thermal data/Thermal_Images.pdf


TROUBLESHOOTING
────────────────

Q: "\.run_demo.ps1 is not recognized"
A: Make sure you include the "." before the filename:
   .\run_demo.ps1  (correct)
   run_demo.ps1    (wrong)

Q: "Flask not found"
A: Install Flask manually:
   pip install flask==3.0.3

Q: "ModuleNotFoundError: No module named 'flask'"
A: Try installing dependencies:
   pip install -r requirements.txt

Q: Server starts but Upload page doesn't load
A: Check that port 5000 isn't in use:
   - Try http://localhost:5000
   - Or restart your browser
   - Or change the port in app.py (line ~20)

Q: GROQ_API_KEY error when generating
A: Add your API key to .env:
   1. Get free key at https://console.groq.com
   2. Edit .env and set GROQ_API_KEY=<your-key>
   3. Restart the Flask server


KEY FILES
──────────
- app.py                  Flask web server
- main.py                 Command-line CLI
- README.md               Full documentation
- requirements.txt        All Python dependencies
- .env.example            Environment template
- run_demo.ps1            Windows startup (PowerShell)
- run_demo.sh             Unix startup (Bash)


SYSTEM REQUIREMENTS
────────────────────
✓ Python 3.11+
✓ Flask 3.0.3+
✓ All dependencies from requirements.txt
✓ Groq API key (free at console.groq.com)
✓ Poppler (for PDF image extraction)
  - Windows: https://github.com/oschwartz10612/poppler-windows/releases/
  - macOS: brew install poppler
  - Linux: sudo apt-get install poppler-utils


MORE INFO
──────────
See README.md for:
- Complete architecture overview
- 5-agent LangGraph pipeline
- Report synthesis details
- Design decisions
- Performance notes


═════════════════════════════════════════════════════
Ready to go! Open http://localhost:5000 in your browser.
═════════════════════════════════════════════════════
