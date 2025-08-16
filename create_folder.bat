@echo off
REM Create project structure for SPY Options Chain application

echo Creating project directories...

REM Create main project folder
mkdir SPY-Options-Chain
cd SPY-Options-Chain

REM Create backend directories
mkdir backend
cd backend
mkdir templates
mkdir static

REM Create backend files
echo # Placeholder > config.py
echo # Placeholder > server.py
echo # Placeholder > ibkr_client.py
echo # Placeholder > order_manager.py
echo # Placeholder > order_routes.py
echo # Placeholder > requirements.txt
echo @echo off > start_backend.bat

cd ..

REM Create frontend directories
mkdir frontend
cd frontend
mkdir public
mkdir src
cd src
mkdir components
mkdir services

REM Create frontend base files
echo // Placeholder > index.js
echo /* CSS styles */ > index.css
echo // Placeholder > config.js

REM Create frontend components
cd components
echo // Placeholder > App.js
echo // Placeholder > ConnectionStatus.js
echo // Placeholder > MultiLegOrderForm.js
echo // Placeholder > Notification.js
echo // Placeholder > OptionsTable.js
echo // Placeholder > OrderForm.js
cd ..

REM Create frontend services
cd services
echo // Placeholder > ApiService.js
echo // Placeholder > SocketService.js
cd ..
cd ..

REM Create frontend config files
echo { "name": "spy-options-chain" } > package.json
echo @echo off > start_frontend.bat

cd ..

REM Create README file
echo # SPY Options Chain Application > README.md

echo Project structure created successfully!
echo.
echo Now you can copy the actual code into these files.
echo.
echo Project structure:
echo SPY-Options-Chain/
echo ├── backend/
echo │   ├── config.py
echo │   ├── ibkr_client.py
echo │   ├── order_manager.py
echo │   ├── order_routes.py
echo │   ├── requirements.txt
echo │   ├── server.py
echo │   └── start_backend.bat
echo ├── frontend/
echo │   ├── package.json
echo │   ├── public/
echo │   ├── src/
echo │   │   ├── components/
echo │   │   │   ├── App.js
echo │   │   │   ├── ConnectionStatus.js
echo │   │   │   ├── MultiLegOrderForm.js
echo │   │   │   ├── Notification.js
echo │   │   │   ├── OptionsTable.js
echo │   │   │   └── OrderForm.js
echo │   │   ├── config.js
echo │   │   ├── index.css
echo │   │   ├── index.js
echo │   │   └── services/
echo │   │       ├── ApiService.js
echo │   │       └── SocketService.js
echo │   └── start_frontend.bat
echo └── README.md