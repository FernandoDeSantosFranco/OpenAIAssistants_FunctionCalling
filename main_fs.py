import streamlit as st
from openai import OpenAI
import os
from dotenv import load_dotenv
import re  # Import regex for string cleaning
import timeit

# Load environment variables
load_dotenv(override=True)

# Initialize OpenAI client
client = OpenAI()

# Retrieve the vector store and assistant
vector_store = client.beta.vector_stores.retrieve(vector_store_id=os.getenv("VECTOR_STORE_ID"))
assistant = client.beta.assistants.retrieve(assistant_id=os.getenv("ASST_ID"))

# Update the assistant to use the vector store
assistant = client.beta.assistants.update(
    assistant_id=assistant.id,
    tool_resources={"file_search": {"vector_store_ids": [vector_store.id]}},
)

# Streamlit App
st.title("Chat with Your Assistant 🤖")

# Initialize session state for chat history and thread ID
if "messages" not in st.session_state:
    st.session_state.messages = []
if "thread_id" not in st.session_state:
    st.session_state.thread_id = None

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# User input
if prompt := st.chat_input("What would you like to ask?"):
    start = timeit.default_timer()

    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Create a thread if it doesn't exist
    if st.session_state.thread_id is None:
        thread = client.beta.threads.create()
        st.session_state.thread_id = thread.id
        thread_id = thread.id  # Define thread_id here
    else:
        thread_id = st.session_state.thread_id  # Use existing thread_id

    # Add the user's message to the thread
    client.beta.threads.messages.create(
        thread_id=thread_id,
        role="user",
        content=prompt
    )

    try:
        # Create and poll the run
        run = client.beta.threads.runs.create_and_poll(
            thread_id=thread_id,
            assistant_id=assistant.id
        )

        # Check if the run completed successfully
        if run.status == 'completed':
            stop = timeit.default_timer()
            print("Time: ", stop - start)

            # Retrieve the assistant's response
            messages = list(client.beta.threads.messages.list(thread_id=thread_id))
            if messages:
                for message in messages:
                    if message.role == "assistant":
                        assistant_response = message.content[0].text.value
                        # Remove citations using regex
                        assistant_response = re.sub(r"【.*?】", "", assistant_response).strip()
                        break

                # Add assistant's response to chat history
                st.session_state.messages.append({"role": "assistant", "content": assistant_response})
                with st.chat_message("assistant"):
                    st.markdown(assistant_response)
            else:
                st.error("No response from the assistant.")
        else:
            st.error(f"Run did not complete successfully. Status: {run.status}")
    except Exception as e:
        st.error(f"An error occurred: {e}")