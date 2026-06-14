"""
Central configuration for the Viral Content Idea Agent.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# --- API Keys ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# --- Reddit Subreddits to Monitor ---
SUBREDDITS = [
    "MachineLearning",
    "ClaudeAI",
    "OpenAI",
    "ArtificialIntelligence",
    "singularity",
    "StableDiffusion",
    "cursor",
    "automation",
    "SideProject",
    "Entrepreneur",
    "ChatGPT",
    "ChatGPTCoding",
    "artificial",
    "deeplearning",
    "learnmachinelearning",
    "MLQuestions",
    "datascience",
    "computervision",
    "NLP",
    "reinforcementlearning",
    "AIAgents",
    "AI_Agents",
    "PromptEngineering",
    "LLMDevs",
    "GPT3",
    "Bard",
    "GeminiAI",
    "perplexity_ai",
    "midjourney",
    "dalle2",
    "runwayml",
    "ElevenLabs",
    "AIVideoCreation",
    "n8n",
    "zapier",
    "SaaS",
    "microsaas",
    "indiehackers",
    "startups",
    "digital_marketing",
    "socialmedia",
    "content_marketing",
    "YoutubeChannelHelp",
    "NewTubers",
    "InstagramMarketing",
    "ArtificialInteligence",
    "AItoolsCatalog",
    "AIethics",
    "OpenSourceAI",
    "huggingface",
    "MachineLearningNews",
    "grok",
    "Mistral",
    "Anthropic",
    "agi",
    "vibecoding",
    "learnAIAgents",
]

# --- X (Twitter) Accounts to Monitor ---
X_ACCOUNTS = [
    "AnthropicAI",
    "sama",
    "karpathy",
    "simonw",
    "swyx",
    "_akhaliq",
    "rohanpaul_ai",
    "ylecun",
    "alexalbert__",
    "TheZvi",
]

# --- Scraping Settings ---
REDDIT_POSTS_PER_SUB = 15       # Number of hot posts to fetch per subreddit
X_TWEETS_PER_ACCOUNT = 10       # Number of recent tweets per account
TOP_POSTS_FOR_AI = 25           # Top ranked posts to send to Gemini
CONTENT_IDEAS_COUNT = 10        # Number of content ideas to generate

# --- Playwright ---
BROWSER_DATA_DIR = os.path.join(os.path.dirname(__file__), "browser_data")
HEADLESS = True                 # Set False to see the browser during scraping

# --- Server ---
HOST = "127.0.0.1"
PORT = 5000
