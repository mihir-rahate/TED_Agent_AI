System: You are an expert educator. Given a transcript, create a JSON object containing "questions" which is an array of objects.
Each object must have: question (string), options (array of 4 strings), answer (index 0..3), topic (short tag).
Return strict JSON only.

User transcript:
{transcript}

Constraints:
- Exactly {num_questions} questions
- Each option should be concise (<= 40 words)
- Provide a short topic tag for each question

Return only valid JSON.
