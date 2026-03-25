#!/bin/bash

# Set colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}Starting Research Agent Application...${NC}"

# 1. Check if Ollama is running
echo -e "${YELLOW}Checking if Ollama is running...${NC}"
# Using tasklist for Windows compatibility
if ! tasklist | findstr /I "ollama.exe" > /dev/null; then
    echo -e "${RED}Ollama is not running!${NC}"
    echo "Please start the Ollama application and ensure it's running before starting the research agent."
    echo "You can download Ollama from https://ollama.com"
    exit 1
fi
echo -e "${GREEN}Ollama is running.${NC}"

# 2. Setup and start Backend
echo -e "${YELLOW}Setting up and starting backend...${NC}"
cd backend || { echo -e "${RED}Backend directory not found!${NC}"; exit 1; }

# Check for python venv
if [ ! -d "venv" ]; then
    echo "Python virtual environment not found. Creating one..."
    py -m venv venv
fi

echo "Starting FastAPI server in the background..."
# Start in a new window for Windows
start "Backend" cmd /c "venv\\Scripts\\activate.bat && uvicorn main:app --reload --port 8000"
cd ..

# Give the backend a moment to start
sleep 3

# 3. Setup and start Frontend
echo -e "${YELLOW}Starting frontend server...${NC}"
cd frontend || { echo -e "${RED}Frontend directory not found!${NC}"; exit 1; }

echo "Starting frontend HTTP server..."
start "Frontend" cmd /c "py -m http.server 3000"
cd ..

echo -e "\n${GREEN}========================================${NC}"
echo -e "${GREEN}Application is running!${NC}"
echo -e "Backend API: ${YELLOW}http://localhost:8000${NC}"
echo -e "Frontend App: ${YELLOW}http://localhost:3000${NC}"
echo -e "${GREEN}========================================${NC}\n"

echo "Two new terminal windows have been opened for the backend and frontend servers."
echo "You can close this window. To stop the servers, close the new terminal windows."

# Keep the script window open for a moment to show the message
sleep 10

