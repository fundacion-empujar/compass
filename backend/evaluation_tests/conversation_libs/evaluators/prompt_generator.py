import textwrap

from evaluation_tests.conversation_libs.evaluators.evaluation_result import EvaluationType


class PromptGenerator:
    """
    Generates the prompt used by the evaluators.
    """

    @staticmethod
    def _get_criteria_string(criteria: EvaluationType):
        match criteria:
            case EvaluationType.CONCISENESS:
                return textwrap.dedent("""
                            Could any of the responses made by EVALUATED_AGENT be expressed more concisely without 
                            losing meaning? Are there any phrases said by EVALUATED_AGENT that are repeated 
                            unnecessarily within this segment of the conversation? Are all the questions by 
                            EVALUATED_AGENT focused and easy to understand?
                        """)
            
            case EvaluationType.FOCUS:
                return textwrap.dedent("""
                            Did the EVALUATED_AGENT lose focus on the topic of the conversation and on its
                            task of investigating the experiences and skill of the user? Did the EVALUATED_AGENT give into
                            a topic of conversation that is different from the experience and skill investigation?
                        """)

            case EvaluationType.SUMMARY_CONSISTENCY:
                return textwrap.dedent("""
                Evaluation Criteria:
                Consistency - the factual alignment between the new summary and the current summary and conversation. 
                A factually consistent new summary contains only statements that are entailed by the current summary and conversation.
                new summaries that contained hallucinated facts are penalized.
                
                Evaluation Steps:

                1. Read the current summary and conversation carefully and identify the main facts and details they present.
                2. Read the new summary and compare it to the current summary and conversation. Check if the new summary contains any factual errors that are not supported by the current summary and conversation.
                3. Assign a score for consistency from of 1 to 5, where 1 is the lowest and 5 is the highest based on the Evaluation Criteria.
                """)

            case EvaluationType.SUMMARY_RELEVANCE:
                return textwrap.dedent("""
                Evaluation Criteria:
                Relevance - selection of important content from the current summary and conversation.
                The new summary should include only important information from the current summary and conversation.
                new summaries which contained redundancies and excess information are penalized.
                
                Evaluation Steps:

                1. Read the summary and the current summary and conversation carefully.
                2. Compare the new summary to the current summary and conversation and identify the main points of the current summary and conversation.
                3. Assess how well the new summary covers the main points of the current summary and conversation, and how much irrelevant or redundant information it contains.
                4. Assign a relevance score from of 1 to 5, where 1 is the lowest and 5 is the highest based on the Evaluation Criteria.
                """)
            case EvaluationType.SINGLE_LANGUAGE:
                return textwrap.dedent("""
                Evaluation Criteria:
                
                Single - Language - Did the EVALUATED_AGENT maintain the same language throughout the conversation? 
                Even if the SIMULATED_USER used a different language.
                
                Evaluation Steps:
                1. Read the conversation carefully and identify the language used by the SIMULATED_USER and EVALUATED_AGENT.
                2. Check if the conversation was in the same language throughout (eg: English, Spanish, French, Swahili, etc)..
                3. Assign a score of 100 if the conversation was in the same language throughout, or 0 otherwise.
                """)

            case EvaluationType.RECAP_CONSISTENCY:
                return textwrap.dedent("""
                Evaluation Criteria:

                Recap Consistency - When the EVALUATED_AGENT presents its final recap of the collected work
                experiences, does it restate ONLY the stored fields for each experience: the job title, the
                work type label (e.g. 'Trabajo asalariado', 'Emprendimiento', 'Trabajo no pago'), the
                company/receiver of the work, and the dates (timeline)? The work type label is a stored field,
                NOT an embellishment. A consistent recap invents nothing. It IS penalized if it adds duties,
                responsibilities, tasks, skills, or achievements, or any specific detail beyond those stored
                fields, EVEN IF the user mentioned that detail earlier in the conversation.
                Only judge the final recap of all experiences (the message where the agent summarizes
                everything collected and asks the user to confirm or change it), not the per-question replies.

                Evaluation Steps:
                1. Find the EVALUATED_AGENT's final recap of all collected work experiences.
                2. For each experience in the recap, check whether it states anything beyond the job title,
                   the work type label, the company/receiver, and the dates.
                3. Penalize every invented or embellished detail (duties, responsibilities, tasks, skills,
                   achievements) that is not one of those stored fields.
                4. Assign a score from 0 to 100, where 100 is a recap that contains only the stored fields
                   and 0 is a recap full of duties/skills beyond those stored fields (even ones the user
                   mentioned earlier in the conversation).
                """)

            case _:
                raise NotImplementedError()

    @staticmethod
    def _get_example_response(criteria: EvaluationType):
        match criteria:
            case EvaluationType.CONCISENESS:
                return textwrap.dedent("""
                            The conversation is somewhat concise, but the EVALUATED_AGENT repeats instructions, 
                    and the SIMULATED_USER could ask more focused questions.
                        """)
            
            case EvaluationType.FOCUS:
                return textwrap.dedent("""
                            The conversation is somewhat focused, but the EVALUATED_AGENT allows the user to drift off at times.
                        """)

            case EvaluationType.SUMMARY_CONSISTENCY:
                return textwrap.dedent("""
               The summary is somewhat consistent, but there are some facts that do not exist on the current conversation.
                """)

            case EvaluationType.SUMMARY_RELEVANCE:
                return textwrap.dedent("""
                The summary is somewhat relevant to the current conversation.
                """)
            case EvaluationType.SINGLE_LANGUAGE:
                return textwrap.dedent("""
                The language used in the conversation is somewhat consistent and it is 'Spanish' mixed with 'English'
                """)

            case EvaluationType.RECAP_CONSISTENCY:
                return textwrap.dedent("""
                The recap is mostly faithful, but the EVALUATED_AGENT added duties the user mentioned in
                passing that are not part of the stored title, company or dates.
                """)
            case _:
                raise NotImplementedError()

    @staticmethod
    def generate_prompt(conversation: str, criteria: EvaluationType) -> str:
        """
        Generates the prompt to be used in the evaluators.
        """
        criteria_string = PromptGenerator._get_criteria_string(criteria)
        example_response = PromptGenerator._get_example_response(criteria)
        if criteria_string is None or example_response is None:
            raise ValueError("Invalid criteria value")

        template = textwrap.dedent(f"""
            You are assessing a conversation between a human (SIMULATED_USER) and a job 
            counselor AI chatbot (EVALUATED_AGENT). {criteria_string}
            
            Rate it from 0 to 100, 0 being worst 100 being best.
                    
            Respond only using a valid JSON format as follows:
            
            {{
                "score": 0, 
                "reason": ""
            }}
            
            Example Response:
            
            {{
                "score": 50,
                "reason": "{example_response}"
            }}
    
            Conversation Data:
            [BEGIN DATA]
            [Conversation]: {conversation}
            [END DATA] 
        """)

        return template

    @staticmethod
    def generate_summary_prompt(conversation: str, current_summary: str, new_summary: str,
            criteria: EvaluationType) -> str:
        """
        Generates the prompt to be used in the summary evaluators.
        """
        criteria_string = PromptGenerator._get_criteria_string(criteria)
        example_response = PromptGenerator._get_example_response(criteria)
        if criteria_string is None or example_response is None:
            raise ValueError("Invalid criteria value")

        template = textwrap.dedent(f"""
            You are assessing a summary that was created from the original conversation. 
            {criteria_string}
                    
            Respond only using a valid JSON format as follows:
            
            {{
                "score": 0, 
                "reason": ""
            }}
            
            Example Response:
            
            {{
                "score": 3,
                "reason": "{example_response}"
            }}
    
            [BEGIN DATA]
            [Current Summary]: {current_summary}
            [Current Conversation]: {conversation}
            [New Summary]: {new_summary}
            [END DATA] 
        """)

        return template
