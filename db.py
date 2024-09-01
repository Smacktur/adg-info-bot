from config import DB_CONFIG  # Импортируй конфигурацию БД
import psycopg2
import logging

logger = logging.getLogger(__name__)

def query_database(request_numbers):
    try:
        query = f"""
        SELECT
            coalesce(arts.constant_id, 'null') as constant_id,
            coalesce(a.stage, 'null') as stage,
            coalesce(a.status, 'null') as status,
            coalesce(arts.initial_channel_id, 'null') as initial_channel_id,
            coalesce(artda.decline_code, 0) as decline_code
        FROM alfa_reject_traffic_sessions arts
        LEFT JOIN applications a ON arts.application_id = a.id
        LEFT JOIN alfa_reject_traffic_declined_applications artda ON arts.constant_id = artda.constant_id
        WHERE arts.constant_id IN ({request_numbers});
        """
        connection = psycopg2.connect(**DB_CONFIG)
        cursor = connection.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()

        results = [
            {
                "constant_id": row[0],
                "stage": row[1],
                "status": row[2],
                "initial_channel_id": row[3],
                "decline_code": row[4]
            } for row in rows
        ]

        cursor.close()
        connection.close()

        return results
    except Exception as e:
        logger.error(f"Ошибка при выполнении запроса в БД: {e}", exc_info=True)
        return []
