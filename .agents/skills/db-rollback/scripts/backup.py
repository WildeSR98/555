import os
import shutil
import datetime
import subprocess
from dotenv import load_dotenv

def backup_database():
    load_dotenv()
    db_type = os.getenv('DB_TYPE', 'sqlite').lower()
    backup_dir = 'backups'
    
    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir)
        print(f"Created backup directory: {backup_dir}")

    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    
    if db_type == 'sqlite':
        db_path = os.getenv('DB_PATH', 'db.sqlite3')
        if not os.path.exists(db_path):
            print(f"Error: SQLite database file not found at {db_path}")
            return False
        
        backup_path = os.path.join(backup_dir, f"{os.path.basename(db_path)}.{timestamp}.bak")
        shutil.copy2(db_path, backup_path)
        print(f"Successfully backed up SQLite database to: {backup_path}")
        return True

    elif db_type == 'postgresql':
        db_name = os.getenv('DB_NAME')
        db_user = os.getenv('DB_USER')
        db_host = os.getenv('DB_HOST', 'localhost')
        db_port = os.getenv('DB_PORT', '5432')
        container_name = 'production_postgres' # From docker-compose.yml
        
        backup_path = os.path.join(backup_dir, f"{db_name}.{timestamp}.sql")
        
        # Try to use docker exec first, as DB is in docker
        print(f"Attempting to backup PostgreSQL from docker container: {container_name}...")
        docker_cmd = [
            'docker', 'exec', '-t', container_name,
            'pg_dump', '-U', db_user, '-F', 'c', db_name
        ]
        
        try:
            with open(backup_path, 'wb') as f:
                subprocess.run(docker_cmd, check=True, stdout=f)
            print(f"Successfully backed up PostgreSQL database from Docker to: {backup_path}")
            return True
        except subprocess.CalledProcessError as e:
            print(f"Docker backup failed, checking local pg_dump... Error: {e}")
            # Fallback to local pg_dump (original logic)
            password = os.getenv('DB_PASSWORD')
            env = os.environ.copy()
            if password:
                env['PGPASSWORD'] = password
                
            cmd = [
                'pg_dump',
                '-h', db_host,
                '-p', db_port,
                '-U', db_user,
                '-F', 'c',
                '-f', backup_path,
                db_name
            ]
            
            try:
                subprocess.run(cmd, check=True, env=env)
                print(f"Successfully backed up PostgreSQL database via local pg_dump to: {backup_path}")
                return True
            except (subprocess.CalledProcessError, FileNotFoundError) as e2:
                print(f"Local backup also failed: {e2}")
                return False
    else:
        print(f"Unknown DB_TYPE: {db_type}")
        return False

if __name__ == "__main__":
    backup_database()
