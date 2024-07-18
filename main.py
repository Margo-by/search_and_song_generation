import autogen
import json
import requests
import openai
import re

from bs4 import BeautifulSoup
from langchain.chat_models import ChatOpenAI
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.chains.summarize import load_summarize_chain
from langchain import PromptTemplate

from config import settings
from suno_api import make_a_song

client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)

config_list = autogen.config_list_from_json(env_or_file="OAI_CONFIG_LIST")
openai.api_key = settings.OPENAI_API_KEY
SERP_API_KEY=settings.SERP_API_KEY

def search(query):
    url = "https://google.serper.dev/search"

    payload = json.dumps({
        "q": query
    })
    headers = {
        'X-API-KEY': SERP_API_KEY ,
        'Content-Type': 'application/json'
    }

    try:
        response = requests.request("POST", url, headers=headers, data=payload)
        response.raise_for_status()  # Raise an error for bad status codes
        response_data = response.json()
        print("search results:", response_data)
        return response_data

    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP error occurred: {http_err}")
    except requests.exceptions.RequestException as req_err:
        print(f"Request exception occurred: {req_err}")

    return None

def clean_scraped_data(html_content):

    # Создание объекта BeautifulSoup
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Удаление всех script и style тегов
    for script_or_style in soup(['script', 'style']):
        script_or_style.decompose()
    
    # Извлечение текста из очищенного HTML
    text = soup.get_text(separator=' ')
    
    # Замена нескольких пробелов одним пробелом
    text = re.sub(r'\s+', ' ', text)
    
    # Удаление пробелов в начале и конце строки
    text = text.strip()
    
    return text

# Глобальный список компаний
companies = []

def get_company(company_name: str, official_site_link: str, contact: str):
    # Создание массива с информацией о компании
    company_info = [company_name, official_site_link, contact]
    
    # Добавление массива в глобальный список компаний
    companies.append(company_info)
    print("company_info: "+ company_info)

def scrape(url: str):
    # scrape website, and also will summarize the content based on objective if the content is too large
    # objective is the original objective & task that user give to the agent, url is the url of the website to be scraped

    print("Scraping website...")
    # Define the headers for the request
    headers = {
        'Cache-Control': 'no-cache',
        'Content-Type': 'application/json',
    }

    # Define the data to be sent in the request
    data = {
        "url": url
    }

    # Convert Python object to JSON string
    data_json = json.dumps(data)

    # Send the POST request
    response = requests.post(
        "https://chrome.browserless.io/content?token=2db344e9-a08a-4179-8f48-195a2f7ea6ee", headers=headers, data=data_json)

    # Check the response status code
    if response.status_code == 200:
        text = clean_scraped_data(response.content)
        print("CONTENTTTTTT:", text)
        if len(text) > 8000:
            output = summary(text)
            return output
        else:
            return text
    else:
        print(f"HTTP request failed with status code {response.status_code}")

def summary(content):
    llm = ChatOpenAI(temperature=0, model="gpt-4o")
    text_splitter = RecursiveCharacterTextSplitter(
        separators=["\n\n", "\n"], chunk_size=10000, chunk_overlap=500)
    docs = text_splitter.create_documents([content])
    map_prompt = """
    Write a detailed summary of the following text for a research purpose:
    "{text}"
    SUMMARY:
    """
    map_prompt_template = PromptTemplate(
        template=map_prompt, input_variables=["text"])

    summary_chain = load_summarize_chain(
        llm=llm,
        chain_type='map_reduce',
        map_prompt=map_prompt_template,
        combine_prompt=map_prompt_template,
        verbose=True
    )

    output = summary_chain.run(input_documents=docs,)

    return output

def research(query):
    llm_config_researcher = {
        "functions": [
            {
                "name": "search",
                "description": "google search for relevant information",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Google search query",
                        }
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "scrape",
                "description": "Scraping website content based on url",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "Website url to scrape",
                        }
                    },
                    "required": ["url"],
                },
            },
            {
                "name": "get_company",
                "description": "Extract company info from the given research material. It is called after the research is completed",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "company_name": {
                            "type": "string",
                            "description": "The full name of the company",
                        },
                        "official_site_link": {
                            "type": "string",
                            "description": "Link to the official website of the company",
                        },
                        "contact": {
                            "type": "string",
                            "description": "email for communication with the company"
                        }
                    },           
                    "required": ["company_name", "official_site_link","contact"],
                },
            },
        ],
        "config_list": config_list}

    researcher = autogen.AssistantAgent(
        name="researcher",
        system_message="""
        Research about a given query.Stop researching as soon as you find all the requested
        and generate detailed research results with loads of technique details with all reference links attached,
        """,
        llm_config=llm_config_researcher,
    )

    user_proxy = autogen.UserProxyAgent(
        name="User_proxy",
        code_execution_config={"use_docker": False},
        human_input_mode="NEVER",
        function_map={
            "search": search,
            "scrape": scrape,
            "get_company": get_company,
        },
        max_consecutive_auto_reply=7
    )

    result=user_proxy.initiate_chat(researcher, message=query)
    print(result)
    # set the receiver to be researcher, and get a summary of the research report
    user_proxy.stop_reply_at_receive(researcher)
    user_proxy.send(
        "Give me the research report that just generated again, return ONLY the report & reference links", researcher)
    # return the last message the expert received
    return user_proxy.last_message()["content"]
def write_song(research_material,topic):
    try:
        response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
            "role": "user",
            "content": [
                {
                "type": "text",
                "text": f"{topic}, here are the material: {research_material}"
                },
            ]
            }
        ],
        #max_tokens=300,
        )
        content = response.choices[0].message.content
        print(content)
        return str(content)
    except Exception as e:
        print(e)
        return None


#Делаем запрос на поиск компании по любым критериям, после выполнения этого запроса в список companies, 
#добавится инфа про название, ссылку на офиц сайт, контакт для связи компании
'''
query_about_company=f"""Найди одну любую компанию, которая активно ведёт соцсети, имеет много информации о 
сотрудниках и основателе на официальном сайте а также email для связи
"""
'''
query_about_company=f"""Найди гомельскую компанию, которая делает Консольно-фрезерные станки
"""
company_info=research(query_about_company)
print(company_info)

print("companies: ")
print(companies)

#достаём первую компанию
company=companies[0][1]

#этот запрос можно кастомизировать если нужна какая-то определённая инфа, инфа может искаться и через любые сайты, через соцсети и т.д.
query=f"""Найди интересную информацитю о компании {company}.
Всего должно быть около 15 фактов, это может быть
1.что нового у них
2.ЧЕМ ГОРДИТСЯ
3.имена важных сотрудников и что о них известно интересного НЕ ПРОСТО ДОЛЖНОСТЬ НО ЧЕМ РАНЬШЕ ЗАНИМАЛСЯ, ХОББИ И Т.Д., 
4.в каком городе расположена
5.С КЕМ КРУТЫМ СОТРУДНИЧАЛИ
6.информация про главу компании, чем занимался, зачем создал компанию, хобби, интересы
7.ПОИЩИ В СОЦ СЕТЯХ ЧЕМ ОНИ СЕЙЧАС ЗАНИМАЮТСЯ, ЧТО НОВОГО произошло в компании в последнее время, 
Если не хватает информации ищи ещё, но не более 15 запросов
должно быть упомянуто не более 5 людей, если больше 3 основателей, то инфу о сотрудниках можно менее подробную искать
"""
#запускается чат, где в последнем сообщении будет содержаться самаризированный результат поиска 
last_message_summary=research(query)
print(last_message_summary)

research_material=last_message_summary

#можно кастомизировать, но учитывай, что максимальный размер песни 3000 символов
topic="сгенерируй песню на русском используя предоставленные факты, включая как можно больше забавной информациио компании, текст должен быть длинной 1000-1500 символов включая пробелы, используй восьмистрочье"
song=write_song(research_material, topic)
print(song)

prompt=song

#можно кастомизировать перечисляя другие жанры, максимальный размер строки 120 символов
tags="jazz"

#максимальная длина 80 символов
title="gift_for_company" +companies[0][0]

#песня генерируется и сохраняется в каталоге songs(нужно зарание проверить что он есть), по id распечатанным можно найти песню на suno
#по полученным ссылкам можно сразу перейти на песню сохранённую в суно 
#всегда создаётся по 2 песни примерно одинаковые, когда просишь 1 сделать и тратится на это 10 кредитов
song_urls=make_a_song(prompt, tags, title)
print(song_urls)

"""
должно получиться что-то вроде
['https://suno.com/song/44b2b855-9bb9-4329-96b7-00be61621a91', 'https://suno.com/song/dab34206-4e36-418c-9116-f276fffc3b82']
18c-9116-f276fffc3b82']
"""