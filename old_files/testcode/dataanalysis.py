# import statements
from dotenv import load_dotenv
from langchain_experimental.agents.agent_toolkits import create_pandas_dataframe_agent
from langchain_google_genai import ChatGoogleGenerativeAI
import pandas as pd

# Load environment variables from a .env file
load_dotenv()

df = pd.read_csv("data/marketing_campaign_dataset.csv")

agent = create_pandas_dataframe_agent(
    ChatGoogleGenerativeAI(temperature=0, model="gemini-2.5-flash"), 
    df, 
    verbose=True,
    allow_dangerous_code=True
)

raw_output = agent.invoke("I want to market electronic products to the customers. Suggest how should I run a campaign?")
print(raw_output)

with open("output.md", "w") as f:
    f.write(raw_output["output"])
    f.close()