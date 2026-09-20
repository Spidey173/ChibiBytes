#!/bin/bash

# --- Color Codes ---
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}====================================================${NC}"
echo -e "${BLUE}🎌 Starting ChibiBytes High-Performance Setup Helper ${NC}"
echo -e "${BLUE}====================================================${NC}"

# Check for python3
if ! command -v python3 &> /dev/null
then
    echo -e "${RED}❌ Error: python3 is not installed on your system. Please install it to proceed.${NC}"
    exit 1
fi

# Detect Python executable path (prefer Python 3.11 if available)
PYTHON_EXE="python3"
if [ -f "/Library/Frameworks/Python.framework/Versions/3.11/bin/python3" ]; then
    PYTHON_EXE="/Library/Frameworks/Python.framework/Versions/3.11/bin/python3"
elif command -v python3.11 &> /dev/null; then
    PYTHON_EXE="python3.11"
fi

echo -e "${GREEN}🐍 Using Python Executable: ${PYTHON_EXE}${NC}"

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo -e "${BLUE}📦 Creating Python virtual environment...${NC}"
    $PYTHON_EXE -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install requirements
echo -e "${BLUE}📥 Installing dependencies...${NC}"
pip install --upgrade pip -q
pip install -r requirements.txt -q

# Check Neon DB Connection String in environment
if grep -q "postgres://" .env 2>/dev/null || grep -q "postgresql://" .env 2>/dev/null; then
    echo -e "${GREEN}☁️ Neon PostgreSQL Cloud Connection String Detected in .env!${NC}"
else
    echo -e "${YELLOW}⚠️ Notice: No DATABASE_URL found in .env. Falling back to local SQLite database.${NC}"
fi

# Run the automated tests to verify stability
echo -e "${BLUE}🧪 Running automated unit test suite...${NC}"
python -m unittest test_app.py

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ All tests passed! Starting server...${NC}"
    
    # Stop any process currently using port 5002
    if lsof -t -i:5002 &> /dev/null; then
        echo -e "${BLUE}🔌 Clearing active process on port 5002...${NC}"
        kill -9 $(lsof -t -i:5002) 2>/dev/null || true
    fi

    echo -e "${GREEN}🚀 Launching ChibiBytes Flask Application at http://localhost:5002${NC}"
    python app.py
else
    echo -e "${RED}❌ Tests failed. Please inspect errors before running.${NC}"
    exit 1
fi

