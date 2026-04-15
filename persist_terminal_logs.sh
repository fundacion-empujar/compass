your_command 2>&1 | ts "%Y-%m-%d %H:%M:%S" | tee -a run.log

yarn start 2>&1 | ts "%Y-%m-%d %H:%M:%S" | tee -a frontend-new-run.log

poetry run python app/server.py 2>&1 | ts "%Y-%m-%d %H:%M:%S" | tee -a backend-run.log