from dotenv import load_dotenv
from aws_langchain.kendra_index_retriever import KendraIndexRetriever
from langchain.chains import ConversationalRetrievalChain
from langchain.chains import LLMChain
from langchain.chains.conversational_retrieval.prompts import CONDENSE_QUESTION_PROMPT, QA_PROMPT
from langchain.chains.question_answering import load_qa_chain
from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler
from langchain.prompts import PromptTemplate
from langchain.llms import Anthropic
import sys
import os

class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

MAX_HISTORY_LENGTH = 5

load_dotenv(dotenv_path="../.env")

def build_chain():
  ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
  region = os.environ["AWS_REGION"]
  kendra_index_id = os.environ["KENDRA_INDEX_ID"]

  llm = Anthropic(temperature=0, anthropic_api_key=ANTHROPIC_API_KEY, max_tokens_to_sample = 512)
  streaming_llm = Anthropic(streaming=True, callbacks=[StreamingStdOutCallbackHandler()], temperature=0, anthropic_api_key=ANTHROPIC_API_KEY)

  retriever = KendraIndexRetriever(kendraindex=kendra_index_id, 
      awsregion=region, 
      return_source_documents=True)

  prompt_template = """

  Human: This is a friendly conversation between a human and an AI. 
  The AI is talkative and provides specific details from its context but limits it to 240 tokens.
  If the AI does not know the answer to a question, it truthfully says it 
  does not know.

  Assistant: OK, got it, I'll be a talkative truthful AI assistant.

  Human: Here are a few documents in <documents> tags:
  <documents>
  {context}
  </documents>
  Based on the above documents, provide a detailed answer for, {question} Answer "don't know" if not present in the document. 

Assistant:
  """
  PROMPT = PromptTemplate(
      template=prompt_template, input_variables=["context", "question"]
  )

  # No qa_prompt in latest langchain ConversationalRetrievalChain
  #qa = ConversationalRetrievalChain.from_llm(llm=llm, retriever=retriever, qa_prompt=PROMPT, return_source_documents=True)
  # Custom prompt https://python.langchain.com/en/latest/modules/chains/index_examples/vector_db_qa.html#custom-prompts
  #qa = ConversationalRetrievalChain.from_llm(llm=llm, retriever=retriever, condense_question_prompt=PROMPT, return_source_documents=True)

  # Construct a ConversationalRetrievalChain with a streaming llm for combine docs
  # and a separate, non-streaming llm for question generation
  question_generator = LLMChain(llm=llm, prompt=CONDENSE_QUESTION_PROMPT)
  doc_chain = load_qa_chain(streaming_llm, chain_type="stuff", prompt=PROMPT)

  qa = ConversationalRetrievalChain(
    retriever=retriever, combine_docs_chain=doc_chain, question_generator=question_generator, return_source_documents=True)

  return qa


def run_chain(chain, prompt: str, history=[]):
  return chain({"question": prompt, "chat_history": history})


if __name__ == "__main__":
  chat_history = []
  qa = build_chain()
  print(bcolors.OKBLUE + "Hello! How can I help you?" + bcolors.ENDC)
  print(bcolors.OKCYAN + "Ask a question, start a New search: or CTRL-D to exit." + bcolors.ENDC)
  print(">", end=" ", flush=True)
  for query in sys.stdin:
    if (query.strip().lower().startswith("new search:")):
      query = query.strip().lower().replace("new search:","")
      chat_history = []
    elif (len(chat_history) == MAX_HISTORY_LENGTH):
      chat_history.pop(0)
    result = run_chain(qa, query, chat_history)
    if result == None or len(result) == 0:
      print("No answer")
      exit

    chat_history.append((query, result["answer"]))
    print(bcolors.OKGREEN + result['answer'] + bcolors.ENDC)
    if 'source_documents' in result:
      print(bcolors.OKGREEN + 'Sources:')
      for d in result['source_documents']:
        print(d.metadata['source'])
    print(bcolors.ENDC)
    print(bcolors.OKCYAN + "Ask a question, start a New search: or CTRL-D to exit." + bcolors.ENDC)
    print(">", end=" ", flush=True)
  print(bcolors.OKBLUE + "Bye" + bcolors.ENDC)
