# 02_using_ollamar.R

# This script demonstrates how to use the ollamar package in R to interact with an LLM.

# Load packages
require(ollamar)
require(dplyr)
require(stringr)

# Select model of interest
MODEL = "smollm2:1.7b"


# Check if model is currently loaded
has_model = list_models() |> 
    filter(str_detect(name, MODEL)) %>%
    nrow() > 0

# If model is not loaded, pull it
if(!has_model) { pull(MODEL) }

# Create a list of messages
messages = create_messages(
    # Start with a system prompt
    create_message(role = "system", content = "You are a talking mouse. Your name is Jerry. You can only talk about mice and cheese."),
    # Add user prompt
    create_message(role = "user", content = "Hello, how are you?")
)

system.time({
    resp = chat(model = MODEL, messages = messages, output = "text", stream = FALSE)
    # append result to chat history
    messages = append_message(x = messages, role = "assistant", content = resp)
})

# View the response
resp

# View the chat history in entirety
messages

# View the chat history in a more readable format
dplyr::bind_rows(messages)

## Convert dataframe chat history back to a list of messages
purrr::transpose(dplyr::bind_rows(messages))

# Clean up shop
rm(list = ls())