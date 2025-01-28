import streamlit as st
from openai import OpenAI
import os
from dotenv import load_dotenv
import re  # Import regex for string cleaning

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

# Initialize session state for chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

import timeit
start = timeit.default_timer()

# User input
if prompt := st.chat_input("What would you like to ask?"):
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Create a thread and send the user's message
    thread = client.beta.threads.create(
        messages=[
            {
                "role": "user",
                "content": prompt,
            }
        ]
    )

    # Create and poll the run
    run = client.beta.threads.runs.create_and_poll(thread_id=thread.id, assistant_id=assistant.id)

    # Check if the run completed successfully
    if run.status == 'completed':
        stop = timeit.default_timer()
        print("Time: ", stop - start)
        # Retrieve the assistant's response
        messages = list(client.beta.threads.messages.list(thread_id=thread.id, run_id=run.id))
        if messages:
            # Extract the text value without annotations
            assistant_response = messages[0].content[0].text.value

            # Remove citations using regex
            # This regex matches patterns like 【4:0†active_positions.json】
            assistant_response = re.sub(r"【.*?】", "", assistant_response).strip()

            # Add assistant's response to chat history
            st.session_state.messages.append({"role": "assistant", "content": assistant_response})
            with st.chat_message("assistant"):
                st.markdown(assistant_response)
        else:
            st.error("No response from the assistant.")
    else:
        st.error(f"Run did not complete successfully. Status: {run.status}")