Backend ACFLP

docker-compose down && docker-compose up -d  

#### Tests
docker compose -f docker-compose.test.yml --profile test up --build --abort-on-container-exit
 ruff check src --output-format=github                                                        
ruff format   

docker cp migrate_real_acflp_data.py acflp-backend-web-1:/app/
docker cp current_data_backup.sql acflp-backend-web-1:/app/   
docker compose exec web python /app/migrate_real_acflp_data.py