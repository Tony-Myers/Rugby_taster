import streamlit as st
from openai import OpenAI
import pandas as pd
import base64
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Retrieve the password, OpenAI API key, and email details from Streamlit secrets
PASSWORD = st.secrets["password"]
OPENAI_API_KEY = st.secrets["openai_api_key"]
SENDER_EMAIL = st.secrets["sender_email"]
EMAIL_PASSWORD = st.secrets["email_password"]
RECEIVER_EMAIL = "tony.myers@staff.newman.ac.uk"

# List of interview topics (modified for rugby taster session context)
interview_topics = [
    "Introduction and background in relation to rugby",
    "Motivation for attending the taster session",
    "Overall experience and atmosphere of the session",
    "Most enjoyable parts of the session",
    "Challenges or difficulties faced",
    "Rating aspect: enjoyment level (1–10)",
    "Perceived impact on willingness to continue with rugby"
]

# Calculate total questions for the progress bar
total_questions = len(interview_topics)

def generate_response(prompt, conversation_history=None):
    """
    Generates a response from the OpenAI model using the prompt and conversation history.
    """
    try:
        if conversation_history is None:
            conversation_history = []

        system_content = """You are an experienced and considerate interviewer focusing on young people's experiences with rugby taster sessions aimed at diversifying the participation base. Use British English in your responses (e.g., 'democratised'). 
Ensure your responses are complete and not truncated. After each user response, provide brief feedback and ask a relevant follow-up question based on their answer. Tailor your questions to the user's previous responses, avoiding repetition and exploring areas they haven't covered. Be adaptive and create a natural flow of conversation."""

        messages = [
            {"role": "system", "content": system_content},
            {"role": "system", "content": f"Interview topics: {interview_topics}"},
            *conversation_history[-6:],  # Include the last 6 exchanges for more context
            {"role": "user", "content": prompt}
        ]

        client = OpenAI(api_key=OPENAI_API_KEY)
        response = client.chat.completions.create(
            model="gpt-4",
            messages=messages,
            max_tokens=110,
            n=1,
            temperature=0.6,
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"An error occurred in generate_response: {str(e)}"

def get_transcript_download_link(conversation):
    """
    Returns a clickable download link for the conversation transcript as a CSV.
    """
    df = pd.DataFrame(conversation)
    csv = df.to_csv(index=False)
    b64 = base64.b64encode(csv.encode()).decode()
    href = f'<a href="data:file/csv;base64,{b64}" download="interview_transcript.csv">Download Transcript</a>'
    return href

def send_email(transcript_csv):
    """
    Sends the given transcript (in CSV format) to Tony Myers's email
    address via a secure SMTP connection.
    """
    subject = "Interview Transcript"
    body = "Please find attached the interview transcript."
    
    # Create the email
    message = MIMEMultipart()
    message["From"] = SENDER_EMAIL
    message["To"] = RECEIVER_EMAIL
    message["Subject"] = subject
    message.attach(MIMEText(body, "plain"))

    # Attach the CSV transcript as text/csv
    attachment_part = MIMEText(transcript_csv, "csv")
    attachment_part.add_header(
        "Content-Disposition",
        "attachment",
        filename="interview_transcript.csv"
    )
    message.attach(attachment_part)

    # Securely send the email
    context = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
        server.login(SENDER_EMAIL, EMAIL_PASSWORD)
        server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, message.as_string())

def main():
    # Password authentication
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if not st.session_state.authenticated:
        password = st.text_input("Enter password to access the interview app:", type="password")
        if st.button("Submit"):
            if password == PASSWORD:
                st.session_state.authenticated = True
                st.success("Access granted.")
            else:
                st.error("Incorrect password.")
        return  # Stop the app here if not authenticated

    # Interview app content (only shown if authenticated)
    st.title("Rugby Taster Session Interview Bot")

    # Initialize session state variables if they don't exist
    if "conversation" not in st.session_state:
        st.session_state.conversation = []
    if "current_question" not in st.session_state:
        st.session_state.current_question = (
            "Thank you for agreeing to speak with us about your recent rugby taster session. "
            "To begin, can you tell me a bit about yourself and any previous experience with rugby or other sports?"
        )
    if "submitted" not in st.session_state:
        st.session_state.submitted = False

    st.write("""
    **Information Sheet and Consent**  
    By ticking yes below, you consent to participate in this interview about your experience in a rugby taster session. 
    Your responses may be anonymously quoted in publications. You may end the interview at any time and request 
    your data be removed by emailing tony.myers@staff.newman.ac.uk. An AI assistant will ask the main questions 
    as well as follow-up probing questions depending on your responses.
    """)

    # Consent checkbox
    consent = st.checkbox("I have read the information sheet and give my consent to participate in this interview.")

    if consent:
        st.write(st.session_state.current_question)

        # Free-text response
        user_answer = st.text_area("Your response:", key=f"user_input_{len(st.session_state.conversation)}")

        # Rating slider for the specific aspect being asked about
        # (You can rename the prompt here to clarify which aspect they're rating)
        user_rating = st.slider(
            "On a scale of 1-10, how would you rate your experience relating to the current question/topic?",
            min_value=1,
            max_value=10,
            value=5
        )

        # Progress bar with label
        completed_questions = len([entry for entry in st.session_state.conversation if entry['role'] == "user"])
        progress_percentage = completed_questions / total_questions
        st.write(f"**Interview Progress: {completed_questions} out of {total_questions} questions answered**")
        st.progress(progress_percentage)

        # Submit button
        if st.button("Submit Answer"):
            if user_answer.strip():
                # Add user's answer + rating to conversation
                combined_user_content = f"Answer: {user_answer}\nRating: {user_rating}"
                st.session_state.conversation.append({"role": "user", "content": combined_user_content})
                
                # Generate AI response
                ai_prompt = (
                    f"User's answer: {user_answer}\n"
                    f"User's rating: {user_rating}\n"
                    f"Provide feedback and ask a follow-up question."
                )
                ai_response = generate_response(ai_prompt, st.session_state.conversation)
                
                # Add AI's response to conversation
                st.session_state.conversation.append({"role": "assistant", "content": ai_response})
                
                # Update current question with AI's follow-up
                st.session_state.current_question = ai_response
                
                # Indicate a successful submission
                st.session_state.submitted = True
                
                st.rerun()
            else:
                st.warning("Please provide an answer before submitting.")

        # End Interview button
        if st.button("End Interview"):
            st.success("Interview completed! Thank you for sharing your rugby taster session experience.")
            st.session_state.current_question = "Interview ended"

            # Convert conversation to CSV and email it
            transcript_csv = pd.DataFrame(st.session_state.conversation).to_csv(index=False)
            send_email(transcript_csv)
            st.info("Your transcript has been emailed to the researcher.")

        # Option to display the transcript
        if st.checkbox("Show Interview Transcript"):
            st.write("**Interview Transcript:**")
            for entry in st.session_state.conversation:
                st.write(f"{entry['role'].capitalize()}: {entry['content']}")
                st.write("---")
            
            # Provide download link for the transcript
            st.markdown(get_transcript_download_link(st.session_state.conversation), unsafe_allow_html=True)

        # Restart Interview button
        if st.button("Restart Interview"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()

if __name__ == "__main__":
    main()
