import openai
from dotenv import find_dotenv, load_dotenv
import os
import time
import logging
from datetime import datetime
import psycopg2
from psycopg2 import sql
import json
import streamlit as st

load_dotenv(override=True)

openai.api_key = os.getenv("OPENAI_API_KEY")

client = openai.OpenAI()
model = "gpt-4o"


def get_location_by_id(location_id):
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

        # Define the query
        query = sql.SQL("SELECT name, address, city, state, zip FROM locations WHERE id = %s AND is_active = True")

        # Execute the query
        cursor.execute(query, (location_id,))

        # Fetch the result
        location = cursor.fetchone()

        # Close the cursor and connection
        cursor.close()
        connection.close()

        if location:
            # Get column names
            colnames = [desc[0] for desc in cursor.description]
            # Convert to a dictionary
            location_dict = dict(zip(colnames, location))
            # Convert to JSON
            location_json = json.dumps(location_dict)
            return f"""Here is some information about the location with id {location_id}:\n\n   
            {location_json} 
            """
        else:
            return None

    except (Exception, psycopg2.DatabaseError) as error:
        print(f"Error: {error}")
        return None


def get_position_by_id(position_id):
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

        # Define the query
        query = sql.SQL("SELECT * FROM positions WHERE id = %s AND is_active = True")

        # Execute the query
        cursor.execute(query, (position_id,))

        # Fetch the result
        position = cursor.fetchone()

        # Get column names
        colnames = [desc[0] for desc in cursor.description]

        # Close the cursor and connection
        cursor.close()
        connection.close()

        if position:
            # Convert to a dictionary
            position_dict = dict(zip(colnames, position))

            # Convert datetime objects to strings
            for key, value in position_dict.items():
                if isinstance(value, datetime):
                    position_dict[key] = value.isoformat()

            # Convert to JSON
            position_json = json.dumps(position_dict)
            return f"""Here is some information about the position with id {position_id}:\n\n   
            {position_json} 
            """
        else:
            return None

    except (Exception, psycopg2.DatabaseError) as error:
        print(f"Error: {error}")
        return None


class AssistantManager:
    thread_id = None
    #assistant_id = None
    assistant_id = os.getenv("ASST_ID")

    def __init__(self, model: str = model):
        self.client = client
        self.model = model
        self.assistant = None
        self.thread = None
        self.run = None
        self.summary = None

        # Retrieve existing assitant and thread if IDs are already defined
        if AssistantManager.assistant_id:
            self.assistant = self.client.beta.assistants.retrieve(
                assistant_id=AssistantManager.assistant_id
            )
        if AssistantManager.thread_id:
            self.thread = self.client.beta.threads.retrieve(
                thread_id=AssistantManager.thread_id
            )

    def create_assistant(self, name, instructions, tools):
        if not self.assistant:
            assistant_obj = self.client.beta.assistants.create(
                name=name, instructions=instructions, tools=tools, model=self.model
            )
            AssistantManager.assistant_id = assistant_obj.id
            self.assistant = assistant_obj
            #print(f"AssisID::::: {self.assistant.id}")

    def create_thread(self):
        if not self.thread:
            thread_obj = self.client.beta.threads.create()
            AssistantManager.thread_id = thread_obj.id
            self.thread = thread_obj
            #print(f"ThreadID::::: {self.thread.id}")

    def add_message_to_thread(self, role, content):
        if self.thread:
            self.client.beta.threads.messages.create(
                thread_id=self.thread.id, role=role, content=content
            )

    def run_assistant(self, instructions):
        if self.thread and self.assistant:
            self.run = self.client.beta.threads.runs.create(
                thread_id=self.thread.id,
                assistant_id=self.assistant.id,
                instructions=instructions,
            )

    def process_message(self):
        if self.thread:
            messages = self.client.beta.threads.messages.list(thread_id=self.thread.id)
            summary = []

            last_message = messages.data[0]
            role = last_message.role
            response = last_message.content[0].text.value
            summary.append(response)

            self.summary = "\n".join(summary)
            #print(f"SUMMARY------> {role.capitalize()}: ==> {response}")

            # for msg in messages:
            #    role = msg.role
            #    content = msg.content[0].text.value
            #    print(f"SUMMARY------> {role.capitalize()}: ==> {content}")

    def call_required_functions(self, required_actions):
        if not self.run:
            return
        tools_outputs = []

        for action in required_actions["tool_calls"]:
            func_name = action["function"]["name"]
            arguments = json.loads(action["function"]["arguments"])

            if func_name == "get_location_by_id":
                output = get_location_by_id(location_id=arguments["location_id"])
                #print(f"STUFFFFF;;;; {output}")
                
                tools_outputs.append({"tool_call_id": action["id"], "output": output})
            
                
            elif func_name == "get_position_by_id":
                output = get_position_by_id(position_id=arguments["position_id"])
                #print(f"STUFFFFF;;;; {output}")

                tools_outputs.append({"tool_call_id": action["id"], "output": output})
            else:
                raise ValueError(f"Unknown function: {func_name}")
        print("Submitting outputs back to the Assistant...")
        self.client.beta.threads.runs.submit_tool_outputs(
            thread_id=self.thread.id, run_id=self.run.id, tool_outputs=tools_outputs
        )

    # For streamlit
    def get_summary(self):
        return self.summary

    def wait_for_completion(self):
        if self.thread and self.run:
            while True:
                time.sleep(5)
                run_status = self.client.beta.threads.runs.retrieve(
                    thread_id=self.thread.id, run_id=self.run.id
                )
                #print(f"RUN STATUS:: {run_status.model_dump_json(indent=4)}")

                if run_status.status == "completed":
                    self.process_message()
                    break

                elif run_status.status == "requires_action":
                    print("FUNCTION CALLING NOW...")
                    self.call_required_functions(
                        required_actions=run_status.required_action.submit_tool_outputs.model_dump()
                    )

    # Run the steps
    def run_steps(self):
        run_steps = self.client.beta.threads.runs.steps.list(
            thread_id=self.thread.id, run_id=self.run.id
        )
        #print(f"Run-Steps::: {run_steps}")
        return run_steps


def main():
    # location = get_location_by_id(1)
    # print(location)

    manager = AssistantManager()

    # Streamlit inferface
    st.title("Locations & Positions retriever")

    with st.form(key="user_input_form"):
        instructions = st.text_input("Enter location_id or position_id:")
        submit_button = st.form_submit_button(label="Send")

        if submit_button:

            import timeit
            start = timeit.default_timer()

            manager.create_assistant(
                name="L&P Assistant",
                instructions="You are a helpful assistant. If you are asked about a location, use the id of the location with the provided get_location_by_id function to get the information about the location, then answer the user's question with that data exclusively. If you are asked about a position, use the id of the position with the provided get_position_by_id function to get the information about the position, then answer the user's question with that data exclusively.",
                tools=[
                    {
                        "type": "function",
                        "function": {
                            "name": "get_location_by_id",
                            "description": "Get details about a location",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "location_id": {
                                        "type": "string",
                                        "description": "The location id",
                                    }
                                },
                                "required": ["location_id"],
                            },
                        },
                    },
                    {
                        "type": "function",
                        "function": {
                            "name": "get_position_by_id",
                            "description": "Get details about a position",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "position_id": {
                                        "type": "string",
                                        "description": "The position id",
                                    }
                                },
                                "required": ["position_id"],
                            },
                        },
                    },
                ],
            )
            manager.create_thread()

            # Add the message and run the assistant
            manager.add_message_to_thread(
                role="user",
                content=f"Summarize the details based on the query and the id: {instructions}",
            )

            manager.run_assistant(instructions="Summarize the details")

            # Wait for completions and process messages
            manager.wait_for_completion()

            summary = manager.get_summary()
            st.write(summary)

            st.text("Run Steps:")
            st.code(manager.run_steps(), line_numbers=True)
            
            stop = timeit.default_timer()

            print('Time: ', stop - start)  


if __name__ == "__main__":
    main()
