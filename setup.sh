#!/bin/bash
set -e

echo ""
echo "  ╔══════════════════════════════════════════╗"
echo "  ║      JARVIS — Setup & Install            ║"
echo "  ╚══════════════════════════════════════════╝"
echo ""

python3 -c "import sys; assert sys.version_info >= (3,10), 'Python 3.10+ required'" \
  || { echo "  ❌ Python 3.10+ required"; exit 1; }
echo "  ✅ Python: $(python3 --version)"

echo ""
echo "  📦 Installing Python packages..."
pip3 install groq python-dotenv --break-system-packages 2>/dev/null || \
pip3 install groq python-dotenv

echo ""
read -p "  Install system tools (wmctrl, xdotool, scrot)? Needs sudo [y/N]: " choice
if [[ "$choice" =~ ^[Yy]$ ]]; then
    sudo apt-get install -y wmctrl xdotool scrot
fi

if [ ! -f ".env" ]; then
    cp .env.example .env
    echo ""
    echo "  📝 Created .env — add your GROQ_API_KEY:"
    echo "     nano .env"
else
    echo "  ✅ .env already exists."
fi

chmod +x main.py

echo ""
echo "  ╔══════════════════════════════════════════╗"
echo "  ║         Setup Complete! 🎉               ║"
echo "  ╚══════════════════════════════════════════╝"
echo ""
echo "  Run:   python3 main.py"
echo "  Debug: JARVIS_DEBUG=1 python3 main.py"
echo ""
