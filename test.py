import psycopg2
import json
from psycopg2 import sql
import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(override=True)

client = OpenAI()


# Helper function to save data as JSON
def save_to_json(data, filename):
    with open(filename, "w") as f:
        json.dump(data, f, indent=4)
    print(f"Data saved to {filename}")


# Function to convert location and position data to a dictionary
def location_with_positions_to_dict(location, position_data):
    return {
        "id": location["id"],
        "name": location["name"],
        "address": location["address"],
        "city": location["city"],
        "state": location["state"],
        "zip": location["zip"],
        "phone": location["phone"],
        "positions_details": position_data,
    }


# Function to fetch all locations and their associated positions
def get_all_locations(connection):
    try:
        with connection.cursor() as cursor:
            # Query all active locations
            cursor.execute(
                """
                SELECT id, name, address, city, state, zip, phone, is_active
                FROM locations
                WHERE is_active = TRUE
            """
            )
            locations = cursor.fetchall()

            # Query distinct active locations for the "all_available_locations" section
            cursor.execute(
                """
                SELECT DISTINCT id, name, city, state
                FROM locations
                WHERE is_active = TRUE
            """
            )
            distinct_locations = cursor.fetchall()

            # Query distinct active positions for the "all_available_positions" section
            cursor.execute(
                """
                SELECT DISTINCT p.id, p.name
                FROM positions p
                JOIN locations_positions lp ON p.id = lp.position_id
                WHERE p.is_active = TRUE
                AND lp.filled_openings < lp.max_openings
            """
            )
            distinct_positions = cursor.fetchall()

            locations_data = []
            locations_by_cities = {}
            locations_by_states = {}

            for location in locations:
                location_dict = {
                    "id": location[0],
                    "name": location[1],
                    "address": location[2],
                    "city": location[3],
                    "state": location[4],
                    "zip": location[5],
                    "phone": location[6],
                }

                # Query positions associated with the current location
                # Filter out inactive positions and positions where filled_openings >= max_openings
                cursor.execute(
                    """
                    SELECT lp.position_id, p.name, p.description, p.key_responsibilities, p.qualifications, p.benefits, p.salary_range,
                            p.salary_currency, p.salary_period, p.job_type, p.location_type, p.is_active, lp.max_openings, lp.filled_openings
                    FROM locations_positions lp
                    JOIN positions p ON lp.position_id = p.id
                    WHERE lp.location_id = %s
                    AND p.is_active = TRUE
                    AND lp.filled_openings < lp.max_openings
                """,
                    (location[0],),
                )
                positions_locations = cursor.fetchall()

                position_data = [
                    {
                        "position_id": pl[0],
                        "name": pl[1],
                        "description": pl[2],
                        "key_responsibilities": pl[3],
                        "qualifications": pl[4],
                        "benefits": pl[5],
                        "salary_range": pl[6],
                        "salary_currency": pl[7],
                        "salary_period": pl[8],
                        "job_type": pl[9],
                        "location_type": pl[10],
                        "max_openings": pl[12],
                        "filled_openings": pl[13],
                    }
                    for pl in positions_locations
                ]

                # Append location data with associated positions
                locations_data.append(
                    location_with_positions_to_dict(location_dict, position_data)
                )

                # Group locations by city
                city = location[3]
                if city not in locations_by_cities:
                    locations_by_cities[city] = []
                locations_by_cities[city].append(
                    {
                        "id": location[0],
                        "name": location[1],
                        "address": location[2],
                        "state": location[4],
                        "zip": location[5]
                    }
                )

                # Group locations by state
                state = location[4]
                if state not in locations_by_states:
                    locations_by_states[state] = []
                locations_by_states[state].append(
                    {
                        "id": location[0],
                        "name": location[1],
                        "address": location[2],
                        "city": location[3],
                        "zip": location[5]

                    }
                )

            # Prepare the final JSON structure
            available_locations_and_positions = {
                "all_available_positions": [
                    {"id": pos[0], "name": pos[1]} for pos in distinct_positions
                ],
                "all_available_locations": [
                    {"id": loc[0], "name": loc[1], "city": loc[2], "state": loc[3]}
                    for loc in distinct_locations
                ],
                "locations_by_city": [
                   {city: locations} for city, locations in locations_by_cities.items()
                ],
                "locations_by_state": [
                   {state: locations}
                   for state, locations in locations_by_states.items()
                ]
            }

            locations_and_positions_details = {"locations_details": locations_data}

            return available_locations_and_positions, locations_and_positions_details

    except psycopg2.Error as e:
        print(f"Error fetching all locations: {e}")
        return {}
    finally:
        if connection:
            connection.close()


# Main execution
if __name__ == "__main__":
    # Database connection parameters
    conn_params = {
        "dbname": os.getenv("dbname"),
        "user": os.getenv("user"),
        "password": os.getenv("password"),
        "host": os.getenv("host"),
        "port": os.getenv("port"),
    }

    # Connect to the database
    conn = psycopg2.connect(**conn_params)

    # Fetch all locations and their positions
    available_locations_and_positions, locations_and_positions_details = (
        get_all_locations(conn)
    )

    # Save the results to JSON files
    save_to_json(available_locations_and_positions, "all_available_locations_and_positions.json")
    save_to_json(
        locations_and_positions_details, "locations_and_positions_details.json"
    )


def load_to_vector_store():
    # Retrieve the vector store
    vector_store = client.beta.vector_stores.retrieve(
        vector_store_id=os.getenv("VECTOR_STORE_ID")
    )

    # Retrieve the list of files in the vector store
    files_in_vs = client.beta.vector_stores.files.list(vector_store_id=vector_store.id)

    files = client.files.list(purpose="assistants")
    for file in files.data:
        client.files.delete(file.id)

    # Delete each file in the vector store
    for file in files_in_vs.data:
        client.beta.vector_stores.files.delete(
            vector_store_id=vector_store.id, file_id=file.id
        )

    # Ready the files for upload to OpenAI
    file_paths = [
        "all_available_locations_and_positions.json",
        "locations_and_positions_details.json",
    ]
    file_streams = [open(path, "rb") for path in file_paths]

    # Use the upload and poll SDK helper to upload the files, add them to the vector store,
    # and poll the status of the file batch for completion.
    file_batch = client.beta.vector_stores.file_batches.upload_and_poll(
        vector_store_id=vector_store.id, files=file_streams
    )

    # You can print the status and the file counts of the batch to see the result of this operation.
    print(file_batch.status)
    print(file_batch.file_counts)


load_to_vector_store()
