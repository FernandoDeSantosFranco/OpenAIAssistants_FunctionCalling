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
    
def simplified_location_with_positions_to_dict(location, position_data):
    return {
        "id": location["id"],
        "name": location["name"],
        "city": location["city"],
        "state": location["state"],
        "zip": location["zip"],
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
            simplified_locations_data = []
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
                
                simplified_location_dict = {
                    "id": location[0],
                    "name": location[1],
                    "city": location[3],
                    "state": location[4],
                    "zip": location[5]
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
                
                
                simplified_position_data = [
                    {
                        "position_id": pl[0],
                        "name": pl[1]
                    }
                    for pl in positions_locations
                ]

                # Append location data with associated positions
                locations_data.append(
                    location_with_positions_to_dict(location_dict, position_data)
                )

                simplified_locations_data.append(
                    simplified_location_with_positions_to_dict(simplified_location_dict, simplified_position_data)
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
                ],
                "list_of_locations_with_positions_available": simplified_locations_data
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
#save_to_json(available_locations_and_positions, "all_available_locations_and_positions.json")
#save_to_json(
#    locations_and_positions_details, "locations_and_positions_details.json"
#)



def load_to_vector_store():
    # Retrieve the vector store
    vector_store = client.beta.vector_stores.retrieve(
        vector_store_id=os.getenv("VECTOR_STORE_ID")
    )

    # Retrieve the list of files in the vector store
    files_in_vs = client.beta.vector_stores.files.list(vector_store_id=vector_store.id)

    # Delete all existing files in the vector store
    for file in files_in_vs.data:
        client.beta.vector_stores.files.delete(
            vector_store_id=vector_store.id, file_id=file.id
        )

    # Delete all existing assistant files (optional, if needed)
    files = client.files.list(purpose="assistants")
    for file in files.data:
        client.files.delete(file.id)

    # Get all .txt files in the current directory
    file_paths = [f for f in os.listdir() if f.endswith(".txt")]

    if not file_paths:
        print("No .txt files found in the current directory.")
        return

    # Open the files in binary mode for upload
    file_streams = [open(path, "rb") for path in file_paths]

    # Use the upload and poll SDK helper to upload the files, add them to the vector store,
    # and poll the status of the file batch for completion.
    file_batch = client.beta.vector_stores.file_batches.upload_and_poll(
        vector_store_id=vector_store.id, files=file_streams
    )

    # Print the status and the file counts of the batch
    print(f"Batch Status: {file_batch.status}")
    print(f"File Counts: {file_batch.file_counts}")

    # Close all file streams
    for stream in file_streams:
        stream.close()


#load_to_vector_store()

# assistant = client.beta.assistants.retrieve(
#     assistant_id=os.getenv("ASST_ID")
# )

# vector_store = client.beta.vector_stores.retrieve(
#     vector_store_id=os.getenv("VECTOR_STORE_ID")
# )

# assistant = client.beta.assistants.update(
#   assistant_id=assistant.id,
#   tool_resources={"file_search": {"vector_store_ids": [vector_store.id]}},
# )

# def available_locations_to_txt():
#     # Define your database connection parameters
#     db_params = {
#         "dbname": os.getenv("dbname"),
#         "user": os.getenv("user"),
#         "password": os.getenv("password"),
#         "host": os.getenv("host"),
#         "port": os.getenv("pg_port"),
#     }

#     try:
#         # Connect to your PostgreSQL database
#         connection = psycopg2.connect(**db_params)
#         cursor = connection.cursor()

#         # Define the query to select all active locations with available positions
#         query = sql.SQL("""
#             SELECT DISTINCT l.id, l.name, l.city, l.state, l.zip
#             FROM locations l
#             JOIN locations_positions lp ON l.id = lp.location_id
#             JOIN positions p ON lp.position_id = p.id
#             WHERE l.is_active = TRUE
#               AND p.is_active = TRUE
#               AND lp.filled_openings < lp.max_openings
#         """)

#         # Execute the query
#         cursor.execute(query)

#         # Fetch all results
#         locations = cursor.fetchall()

#         # Get column names
#         colnames = [desc[0] for desc in cursor.description]

#         # Close the cursor and connection
#         cursor.close()
#         connection.close()

#         if locations:
#             # Group locations by state and city
#             state_groups = {}
#             city_groups = {}

#             for location in locations:
#                 location_dict = dict(zip(colnames, location))
#                 state = location_dict['state']
#                 city = location_dict['city']

#                 # Add to state group
#                 if state not in state_groups:
#                     state_groups[state] = []
#                 state_groups[state].append(location_dict)

#                 # Add to city group
#                 if city not in city_groups:
#                     city_groups[city] = []
#                 city_groups[city].append(location_dict)

#             # Write files for each state
#             for state, locations_in_state in state_groups.items():
#                 state_filename = f"available_locations_in_{state}_state.txt"
#                 text_data = f"Available Locations in {state}:\n\n"
#                 for location in locations_in_state:
#                     text_data += f"ID: {location['id']}\n"
#                     text_data += f"Name: {location['name']}\n"
#                     text_data += f"City: {location['city']}\n"
#                     text_data += f"State: {location['state']}\n"
#                     text_data += f"Zip: {location['zip']}\n"
#                     text_data += "\n"  # Separator between locations

#                 with open(state_filename, "w") as file:
#                     file.write(text_data)
#                 print(f"File written: {state_filename}")

#             # Write files for each city
#             for city, locations_in_city in city_groups.items():
#                 city_filename = f"available_locations_in_{city}_city.txt"
#                 text_data = f"Available Locations in {city}:\n\n"
#                 for location in locations_in_city:
#                     text_data += f"ID: {location['id']}\n"
#                     text_data += f"Name: {location['name']}\n"
#                     text_data += f"City: {location['city']}\n"
#                     text_data += f"State: {location['state']}\n"
#                     text_data += f"Zip: {location['zip']}\n"
#                     text_data += "\n"  # Separator between locations

#                 with open(city_filename, "w") as file:
#                     file.write(text_data)
#                 print(f"File written: {city_filename}")

#             return "Files generated successfully."

#         else:
#             print("No active locations with available positions found.")
#             return "No active locations with available positions found."

#     except (Exception, psycopg2.DatabaseError) as error:
#         print(f"Error: {error}")
#         return f"Error: {error}"
    
    
def generate_grouped_available_locations_files():
    # Define your database connection parameters
    db_params = {
        "dbname": os.getenv("dbname"),
        "user": os.getenv("user"),
        "password": os.getenv("password"),
        "host": os.getenv("host"),
        "port": os.getenv("pg_port"),
    }

    try:
        # Connect to your PostgreSQL database
        connection = psycopg2.connect(**db_params)
        cursor = connection.cursor()

        # Define the query to select all active locations with available positions
        query = sql.SQL("""
            SELECT DISTINCT l.id, l.name, l.city, l.state, l.zip
            FROM locations l
            JOIN locations_positions lp ON l.id = lp.location_id
            JOIN positions p ON lp.position_id = p.id
            WHERE l.is_active = TRUE
              AND p.is_active = TRUE
              AND lp.filled_openings < lp.max_openings
        """)

        # Execute the query
        cursor.execute(query)

        # Fetch all results
        locations = cursor.fetchall()

        # Get column names
        colnames = [desc[0] for desc in cursor.description]

        # Close the cursor and connection
        cursor.close()
        connection.close()

        if locations:
            # Group locations by state and city
            state_groups = {}
            city_groups = {}

            for location in locations:
                location_dict = dict(zip(colnames, location))
                state = location_dict['state']
                city = location_dict['city']

                # Add to state group
                if state not in state_groups:
                    state_groups[state] = []
                state_groups[state].append(location_dict)

                # Add to city group
                if city not in city_groups:
                    city_groups[city] = []
                city_groups[city].append(location_dict)

            # Write all available locations grouped by state to a file
            with open("all_available_locations_by_state.txt", "w") as state_file:
                for state, locations_in_state in state_groups.items():
                    state_file.write(f"Available locations in {state} state:\n\n")
                    for location in locations_in_state:
                        state_file.write(f"id: {location['id']},\n")
                        state_file.write(f"name: {location['name']},\n")
                        state_file.write(f"city: {location['city']},\n")
                        state_file.write(f"state: {location['state']},\n")
                        state_file.write("\n")  # Separator between locations
                    state_file.write("\n")  # Separator between states
            print("File 'all_available_locations_by_state.txt' generated successfully.")

            # Write all available locations grouped by city to a file
            with open("all_available_locations_by_city.txt", "w") as city_file:
                for city, locations_in_city in city_groups.items():
                    city_file.write(f"Available locations in {city} city:\n\n")
                    for location in locations_in_city:
                        city_file.write(f"id: {location['id']},\n")
                        city_file.write(f"name: {location['name']},\n")
                        city_file.write(f"city: {location['city']},\n")
                        city_file.write(f"state: {location['state']},\n")
                        city_file.write("\n")  # Separator between locations
                    city_file.write("\n")  # Separator between cities
            print("File 'all_available_locations_by_city.txt' generated successfully.")

            return "Files generated successfully."

        else:
            print("No active locations with available positions found.")
            return "No active locations with available positions found."

    except (Exception, psycopg2.DatabaseError) as error:
        print(f"Error: {error}")
        return f"Error: {error}"



def generate_positions_available_for_locations():
    # Define your database connection parameters
    db_params = {
        "dbname": os.getenv("dbname"),
        "user": os.getenv("user"),
        "password": os.getenv("password"),
        "host": os.getenv("host"),
        "port": os.getenv("pg_port"),
    }

    try:
        # Connect to your PostgreSQL database
        connection = psycopg2.connect(**db_params)
        cursor = connection.cursor()

        # Define the query to select all active locations with their available positions
        query = sql.SQL("""
            SELECT l.id AS location_id, l.name AS location_name, p.id AS position_id, p.name AS position_name
            FROM locations l
            JOIN locations_positions lp ON l.id = lp.location_id
            JOIN positions p ON lp.position_id = p.id
            WHERE l.is_active = TRUE
              AND p.is_active = TRUE
              AND lp.filled_openings < lp.max_openings
            ORDER BY l.id, p.id
        """)

        # Execute the query
        cursor.execute(query)

        # Fetch all results
        results = cursor.fetchall()

        # Get column names
        colnames = [desc[0] for desc in cursor.description]

        # Close the cursor and connection
        cursor.close()
        connection.close()

        if results:
            # Group positions by location
            location_groups = {}
            for row in results:
                row_dict = dict(zip(colnames, row))
                location_id = row_dict['location_id']
                location_name = row_dict['location_name']

                if location_id not in location_groups:
                    location_groups[location_id] = {
                        "location_name": location_name,
                        "positions": []
                    }
                location_groups[location_id]["positions"].append({
                    "id": row_dict['position_id'],
                    "name": row_dict['position_name']
                })

            # Write positions available for each location to a file
            with open("positions_available_for_locations.txt", "w") as file:
                for location_id, data in location_groups.items():
                    file.write(f"Positions available for {data['location_name']} (Location id: {location_id}):\n\n")
                    for position in data["positions"]:
                        file.write(f"id: {position['id']},\n")
                        file.write(f"name: {position['name']}.\n")
                        file.write("\n")  # Separator between positions
                    file.write("\n")  # Separator between locations
            print("File 'positions_available_for_locations.txt' generated successfully.")
            return "File generated successfully."

        else:
            print("No positions available for any location.")
            return "No positions available for any location."

    except (Exception, psycopg2.DatabaseError) as error:
        print(f"Error: {error}")
        return f"Error: {error}"
    
    
    


import os
import psycopg2
from psycopg2 import sql

def all_available_positions_details(filename="all_available_positions_details.txt"):
    # Define los parámetros de conexión a la base de datos
    db_params = {
        "dbname": os.getenv("dbname"),
        "user": os.getenv("user"),
        "password": os.getenv("password"),
        "host": os.getenv("host"),
        "port": os.getenv("pg_port"),
    }

    try:
        # Conéctate a la base de datos PostgreSQL
        connection = psycopg2.connect(**db_params)
        cursor = connection.cursor()

        # Define la consulta SQL
        query = sql.SQL("""
            SELECT DISTINCT
                lp.position_id, 
                p.name, 
                p.description, 
                p.key_responsibilities, 
                p.qualifications, 
                p.benefits, 
                p.salary_range,
                p.salary_currency, 
                p.salary_period, 
                p.job_type, 
                p.location_type
            FROM positions p
            JOIN locations_positions lp ON p.id = lp.position_id
            WHERE p.is_active = TRUE
              AND lp.filled_openings < lp.max_openings
        """)

        # Ejecuta la consulta
        cursor.execute(query)
        positions = cursor.fetchall()
        colnames = [desc[0] for desc in cursor.description]

        # Cierra la conexión a la base de datos
        cursor.close()
        connection.close()

        if positions:
            # Convierte los resultados en una lista de diccionarios
            positions_list = [dict(zip(colnames, position)) for position in positions]

            # Escribe los detalles en un archivo de texto
            with open(filename, "w", encoding="utf-8") as file:
                for position in positions_list:
                    file.write(f"Position ID: {position['position_id']}\n")
                    file.write(f"Name: {position['name']}\n")
                    file.write(f"Description: {position['description']}\n")
                    
                    # Formatear key_responsibilities si es una lista y no es None
                    key_responsibilities = position.get('key_responsibilities')
                    if key_responsibilities is not None:
                        if isinstance(key_responsibilities, list):
                            key_responsibilities = "; ".join(key_responsibilities)
                        file.write(f"Key Responsibilities: {key_responsibilities}\n")

                    # Formatear qualifications si es una lista y no es None
                    qualifications = position.get('qualifications')
                    if qualifications is not None:
                        if isinstance(qualifications, list):
                            qualifications = "; ".join(qualifications)
                        file.write(f"Qualifications: {qualifications}\n")

                    # Formatear los beneficios si son una lista y no es None
                    benefits = position.get('benefits')
                    if benefits is not None:
                        if isinstance(benefits, list):
                            benefits = "; ".join(benefits)
                        file.write(f"Benefits: {benefits}\n")

                    # Formatear la información del salario si no es None
                    salary_range = position.get('salary_range')
                    salary_currency = position.get('salary_currency')
                    salary_period = position.get('salary_period')

                    if salary_range is not None:
                        salary_info = f"{salary_range}"
                        if salary_currency:
                            salary_info += f" {salary_currency}"
                        if salary_period:
                            salary_info += f" per {salary_period}"
                        file.write(f"Salary Range: {salary_info}\n")

                    # Escribir job_type si no es None
                    job_type = position.get('job_type')
                    if job_type is not None:
                        file.write(f"Job Type: {job_type}\n")

                    # Escribir location_type si no es None
                    location_type = position.get('location_type')
                    if location_type is not None:
                        file.write(f"Location Type: {location_type}\n")

                    file.write("\n")  # Separador entre posiciones
            
            print(f"File '{filename}' generated succesfully.")
        else:
            print("No hay posiciones activas con vacantes disponibles.")

    except (Exception, psycopg2.DatabaseError) as error:
        print(f"Error: {error}")


# Llamar a la función
all_available_positions_details()
generate_positions_available_for_locations()
generate_grouped_available_locations_files()
#load_to_vector_store()
    
