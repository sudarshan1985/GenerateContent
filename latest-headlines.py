# Author: Sudarshan Srivathsav
# Date: May 9th, 2023
# Description: This Python script automates content generation and publishing for GeekTechBlogs.com.
# It utilizes the OpenAI GPT-4 API, NewsAPI, Unsplash API, and YouTube API to generate
# engaging, well-researched, and contextually relevant content. The script fetches trending
# technology topics from popular sources, incorporates current facts, and embeds related
# images and videos to create a rich multimedia experience for the readers.

import openai
from wordpress_xmlrpc import Client, WordPressPost
from wordpress_xmlrpc.methods.posts import NewPost
from wordpress_xmlrpc.methods.taxonomies import GetTerms
from wordpress_xmlrpc.methods.media import UploadFile
import requests
import xmlrpc.client

# Additional libraries and API keys
from newsapi import NewsApiClient
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Set up YouTube API
youtube_api_key = "<YOUR-YOUTUBE-API-KEY>"

# Set up OpenAI API credentials
openai.api_key = "<YOUR-OPEN-API-KEY>"

# Set up WordPress credentials
wp_url = "https://www.yourwpwebsite.com/xmlrpc.php"
wp_username = "YOURUSER"
wp_password = "YOURPASSWORD"
wp_client = Client(wp_url, wp_username, wp_password)

# Set up NewsAPI
newsapi = NewsApiClient(api_key='YOURNEWSAPI-KEY')

# Set up Unsplash API
image_api_key = "YOUR-UNSPLASH-KEY"
image_base_url = "https://api.unsplash.com/search/photos"

# Fetch relevant image
def get_image_url(query):
    headers = {"Authorization": f"Client-ID {image_api_key}"}
    params = {"query": query, "per_page": 1}
    response = requests.get(image_base_url, headers=headers, params=params)
    data = response.json()

    if data['results']:
        return data['results'][0]['urls']['regular']
    return None

# Fetch current facts
def get_current_facts(topic):
    articles = newsapi.get_everything(q=topic, language='en', sort_by='relevancy', page=1, page_size=3)
    facts = []

    for article in articles['articles']:
        if article['title'] and article['url']:
            facts.append({"title": article['title'], "url": article['url']})
    return facts

# Fetch top 10 TechCrunch headlines
def get_techcrunch_headlines():
    headlines = newsapi.get_top_headlines(sources='techcrunch', page_size=5)
    return [article['title'] for article in headlines['articles']]

def get_the_verge_headlines():
    headlines = newsapi.get_top_headlines(sources='the-verge', page_size=5)
    return [article['title'] for article in headlines['articles']]

def get_the_mashable_headlines():
    headlines = newsapi.get_top_headlines(sources='mashable', page_size=5)
    return [article['title'] for article in headlines['articles']]

def get_the_engadget_headlines():
    headlines = newsapi.get_top_headlines(sources='engadget', page_size=5)
    return [article['title'] for article in headlines['articles']]

# Fetch and format current facts, and generate blog content
def generate_blog_content(topic, num_prompts=4):
    facts = get_current_facts(topic)
    formatted_facts = '\n\n'.join([f"- {fact['title']} ([source]({fact['url']}))" for fact in facts])

    prompt_base = f"Write a 2-page long blog post about the trending technology topic: {topic}. Include the following current facts:\n\n{formatted_facts}\n\n---\n\n"

    content = ""
    for _ in range(num_prompts):
        response = openai.Completion.create(engine="text-davinci-003", prompt=prompt_base, max_tokens=3400, n=1, stop=None, temperature=0.7)
        text = response.choices[0].text.strip()
        
        # Remove conclusion-like phrases
        conclusion_phrases = ["In conclusion,", "Overall,", "In summary,", "To sum up,", "Thanks for reading,"]
        for phrase in conclusion_phrases:
            text = text.replace(phrase, "")

        content += text
        prompt_base = f"Continue writing the blog post about {topic}:\n\n{text[-500:]}\n\n---\n\n"

    return content.strip()


# Function to get YouTube video ID
def get_youtube_video_id(query, youtube_api_key):
    youtube = build("youtube", "v3", developerKey=youtube_api_key)

    try:
        response = youtube.search().list(
            q=query,
            part="id,snippet",
            maxResults=1,
            type="video",
        ).execute()

        if response["items"]:
            return response["items"][0]["id"]["videoId"]
        return None

    except HttpError as error:
        print(f"An error occurred: {error}")
        return None


def generate_blog_title(topic, blog_content):
    prompt_title = f"Generate a catchy and relevant title for a blog post about {topic}. The content of the blog post is:\n\n{blog_content[:500]}\n\n---\n\n"
    response_title = openai.Completion.create(engine="text-davinci-003", prompt=prompt_title, max_tokens=50, n=1, stop=None, temperature=0.7)
    return response_title.choices[0].text.strip()

# Main part
techcrunch_headlines =  get_techcrunch_headlines()


for topic in techcrunch_headlines:
    # Get relevant image URL
    image_url = get_image_url(topic)
    image_data = requests.get(image_url).content if image_url else None

    # Generate blog content
    blog_content = generate_blog_content(topic)

    # Add YouTube video at the beginning of the content
    video_id = get_youtube_video_id(topic, youtube_api_key)
    if video_id:
        youtube_embed = f'<iframe width="560" height="315" src="https://www.youtube.com/embed/{video_id}" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>'
        blog_content = f"{youtube_embed}\n\n{blog_content}"

    # Generate blog title
    blog_title = generate_blog_title(topic, blog_content)
   
    # Generate tags and categories
    prompt_tags = f"List 5 relevant tags for a blog post about {topic}, separated by commas:"
    response_tags = openai.Completion.create(engine="text-davinci-003", prompt=prompt_tags, max_tokens=50, n=1, stop=None, temperature=0.7)
    tags = [tag.strip() for tag in response_tags.choices[0].text.split(',')]

    prompt_categories = f"List 1-2 relevant categories for a blog post about {topic}, separated by commas:"
    response_categories = openai.Completion.create(engine="text-davinci-002", prompt=prompt_categories, max_tokens=50, n=1, stop=None, temperature=0.7)
    categories = [category.strip() for category in response_categories.choices[0].text.split(',')]

    post = WordPressPost()
    post.title = blog_title
    post.content = blog_content
    post.terms_names = {
        'post_tag': tags,
        'category': categories,
    }

    # Upload and attach image to the post
    if image_data:
        image_name = f"{topic.replace(' ', '_')}.jpg"
        data = {
            'name': image_name,
            'type': 'image/jpeg',
            'bits': xmlrpc.client.Binary(image_data),
            'overwrite': True,
        }
        response = wp_client.call(UploadFile(data))
        post.thumbnail = response['id']

    post.post_status = 'publish'
    post_id = wp_client.call(NewPost(post))
