from config import *
from util import *
from urllib.parse import quote, unquote
import random
import aiohttp
import asyncio
import sys, os
import time
import regex

#Got this off StackOverflow, stops "Event Loop is Closed" errors
import platform
if (platform.system() == "Windows"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

inputFile = open(sys.argv[1], "rt")
inputText = inputFile.read()
outputFile = open(sys.argv[2], "wt")
outputText = ""

rev_sp_nl = regex.compile('(?r)[ \n]') # Search the string in reverse for either a space or newline.
rev_url_sp_nl = regex.compile('(?r)(%20|%0A)') # Search the string for a hex code that does not match a space or newline.
not_sp_nl = regex.compile('[^ \n]') # Search the string for a character that does not match a space or newline.
rev_not_sp_nl = regex.compile('(?r)[^ \n]') # Search the string in reverse for a character that does not match a space or newline.


nl_tab = regex.compile('[\n\t]') # Search the string in reverse for either a tab or newline.
not_sp_nl_tab = regex.compile('[^ \n\t]') # Search the string for a character that does not match a space, tab, or newline.
rev_not_sp_nl_tab = regex.compile('(?r)[^ \n\t]') # Search the string in reverse for a character that does not match a space, tab, or newline.



        
# Unpack the language information from config.py.
GOOGLE_LANGUAGE_DICT = GOOGLE_LANGUAGE_DICT
GOOGLE_LANGUAGE_GROUPS = GOOGLE_LANGUAGE_GROUPS
current_language_group = DEFAULT_GOOGLE_LANGUAGE_GROUP
GOOGLE_LANGUAGE_NAMES = []
GOOGLE_LANGUAGE_ALL = []
GOOGLE_LANGUAGE_USE = []
for name in GOOGLE_LANGUAGE_DICT:
    GOOGLE_LANGUAGE_NAMES += (name,)
    GOOGLE_LANGUAGE_ALL += (GOOGLE_LANGUAGE_DICT[name][0],)
    if GOOGLE_LANGUAGE_DICT[name][1] == True:
        GOOGLE_LANGUAGE_USE += (GOOGLE_LANGUAGE_DICT[name][0],)

GOOGLE_LANGUAGE_GROUP_NAMES = [group for group in GOOGLE_LANGUAGE_GROUPS]

# Information for translations generator gui.
current_obfucations_value = DEFAULT_OBFUSCATIONS_VALUE
current_multi_obfuscate_mode = DEFAULT_MULTI_OBFUSCATE_MODE


# ----------------------------------------------------------------------------------------------------------------------------------------
# The text in this function is split by the length set in config.py (The default is 5000, which is also the maximum.)
# ----------------------------------------------------------------------------------------------------------------------------------------
# During the splitting process, it looks for newlines or spaces to split at (preventing words from breaking),
# and the split characters are stored in a list to add after the translation is complete, ensuring that
# Google Translate will not mess up the formatting.
# ----------------------------------------------------------------------------------------------------------------------------------------
# Unfortunately this process will not preserve tabs, as tabs are deleted by Google Translate.
# The solution to this requires a different approach which defeats the purpose of this mode
# (which is to minimize the number of requests by maximizing the length).
# ----------------------------------------------------------------------------------------------------------------------------------------
# Luckily newlines and spaces are handled properly, which should suit the needs of most translations, small and large.
# ----------------------------------------------------------------------------------------------------------------------------------------
# After it is split, it is passed into the obfuscate function, where each piece is translated asynchronously and with different languages.
# ----------------------------------------------------------------------------------------------------------------------------------------
async def obfuscate_length_split(text, itr, lang='en'):
    # Area with only spaces, tabs, or newlines before text -> "pre_text".
    start_ind = not_sp_nl_tab.search(text).start()
    pre_text = text[:start_ind]
    
    # Area with only spaces, tabs, or newlines after text -> "post_text".
    end_ind = rev_not_sp_nl.search(text).end()
    post_text = text[end_ind:]

    # Text to translate.
    text = text[start_ind:end_ind]

    text = text.replace('/','⁄') # Replace slashes because Lingva Translate's API can't handle quoted slashes in queries. :/
    rind = ind = 0
    text_len = len(text)
    Text_List = [] # Text pieces stored here.
    Split_List = [] # Split chars stored here.
    while True:
        ind += DEFAULT_SPLIT_LENGTH
        if ind >= text_len:
            Text_List += (text[rind:ind],) # Text
            Split_List += ('',) # Last part is always empty.
            break
        real_length_dif = len(text[rind:ind].encode('utf-16'))//2 - DEFAULT_SPLIT_LENGTH  # Find the length of the text in utf-16 since Google Translate counts emoji's as multiple characters under this standard.
        if real_length_dif > 0:
            ind -= real_length_dif
        if text[ind] not in [" ","\n"]:
            if "\n" in text[rind:ind] or " " in text[rind:ind]:
                ind = rev_sp_nl.search(text[:ind]).start() # Get to space or newline.
                next_pos = ind+not_sp_nl.search(text[ind:]).start() # End of split.
                ind = rev_not_sp_nl.search(text[:ind]).end() # Start of split.
            else: # If no spaces or newlines available, split at current position.
                next_pos = ind
        else:
            next_pos = ind+not_sp_nl.search(text[ind:]).start() # End of split.
            ind = rev_not_sp_nl.search(text[:ind]).end() # Start of split.
        Text_List += (text[rind:ind],) # Text
        Split_List += (text[ind:next_pos],) # Split (newlines and spaces) or (empty).
        ind = rind = next_pos


    # Find the total amount of translations to complete the requested obfuscuation.
    FULL = len(Text_List)*(itr+1)


    async with aiohttp.ClientSession() as session: # Run asynchronous requests for each text piece in the list to speed up result retrieval.
        tasks = [asyncio.ensure_future(obfuscate(session, text_piece, itr, lang)) for text_piece in Text_List]

        Results = await asyncio.gather(*tasks)

    return pre_text+''.join([x for y in zip(Results, Split_List) for x in y]).replace('⁄','/')+post_text # Combine results with split chars.



# ----------------------------------------------------------------------------------------------------------------------------------------
# The text in this function is split by newline and tab characters.
# ----------------------------------------------------------------------------------------------------------------------------------------
# During the splitting process, it looks for newlines and tabs to split the text at, and any characters (newline, tabs, or spaces) within
# the split regions are held in the split list to add after the translation, preventing formatting issues from Google Translate.
# ----------------------------------------------------------------------------------------------------------------------------------------
# This process preserves the formatting of texts with newlines and tabs, while also providing a greater variety in the translations,
# as each individual line or tabsplit piece has a unique set of translations for the obfuscation.
# ----------------------------------------------------------------------------------------------------------------------------------------
# Unfortunately, the downside to this is that the number of requests will tend to be far higher than the split by length approach,
# which leads to a longer translation time. Use this if you are willing to wait longer for a cleaner result with more variety.
# ----------------------------------------------------------------------------------------------------------------------------------------
# After it is split, it is passed into the obfuscate function, where each piece is translated asynchronously and with different languages.
# ----------------------------------------------------------------------------------------------------------------------------------------
async def obfuscate_newline_split(text, itr, lang='en'):
    # Area with only spaces, tabs, or newlines before text -> "pre_text".
    start_ind = not_sp_nl_tab.search(text).start()
    pre_text = text[:start_ind]
    
    # Area with only spaces, tabs, or newlines after text -> "post_text".
    end_ind = rev_not_sp_nl_tab.search(text).end()
    post_text = text[end_ind:]

    # Text to translate.
    text = text[start_ind:end_ind]

    text = text.replace('\r','').replace('/','⁄') # Replace slashes because Lingva Translate's API can't handle quoted slashes in queries. :/

    Text_List = [] # Text pieces stored here.
    Split_List = [] # Split chars stored here.
    rind = ind = 0

    while True:
        if not ("\n" in text[ind:] or "\t" in text[ind:]):
            Text_List += (text[rind:],) # Text
            Split_List += ('',) # Last part is always empty.
            break
        ind = nl_tab.search(text[ind:]).start()+ind # Start of split.
        Text_List += (text[rind:ind],) # Text
        next_pos = not_sp_nl_tab.search(text[ind:]) # End of split.
        if next_pos == None:
            next_pos = len(text) # End of text.
            Split_List += (text[ind:next_pos],) # Split
            break
        next_pos = next_pos.start()+ind # End of split.
        Split_List += (text[ind:next_pos],) # Split.
        rind = ind = next_pos # Reset indicies.

    if Text_List[0] == '': # Delete first string from translation if empty.
        Text_List = Text_List[1:]
    
    # Find the total amount of translations to complete the requested obfuscuation.
    FULL = len(Text_List)*(itr+1)

    async with aiohttp.ClientSession() as session: # Run asynchronous requests for each text piece in the list to speed up result retrieval.
        tasks = [asyncio.ensure_future(obfuscate(session, text_piece, itr, lang)) for text_piece in Text_List]

        Results = await asyncio.gather(*tasks)

    return pre_text+''.join([x for y in zip(Results, Split_List) for x in y]).replace('⁄','/')+post_text # Run asynchronous requests for each text piece in the list to speed up result retrieval.


async def get_translation(session, url): # Gets translation for obfuscate function.
    while True:
        try:
            async with session.get(url) as response:
                try:
                    return (await response.json())['translation'].replace('/','⁄')
                except Exception as e:
                    #url += '%2E'
                    print("Session Error", e)
                    time.sleep(1)
        except (aiohttp.ServerDisconnectedError, aiohttp.ClientResponseError,aiohttp.ClientConnectorError) as e:
            print("Connection Error", e)
            await asyncio.sleep(1)


async def obfuscate(session, text, itr, lang='en'):
    # Area with only spaces, tabs, or newlines before text -> "pre_text".
    start_ind = not_sp_nl_tab.search(text).start()
    pre_text = text[:start_ind]
    
    # Area with only spaces, tabs, or newlines after text -> "post_text".
    end_ind = rev_not_sp_nl.search(text).end()
    post_text = text[end_ind:]

    # Text to translate.
    text = text[start_ind:end_ind]


    if "/" in text:
        text = text.replace('\r','').replace('/','⁄') # Replace slashes because Lingva Translate's API can't handle quoted slashes in queries. :/
    Languages_List = [lang] # List for languages to translate text through.
    last_ind = 0
    for i in range(itr): # Adds languages to list.
        if Languages_List[i-1] in GOOGLE_LANGUAGE_USE:
            last_ind = GOOGLE_LANGUAGE_USE.index(Languages_List[i-1]) # Last language index.
        Languages_List += (random.choice(GOOGLE_LANGUAGE_USE[:last_ind]+GOOGLE_LANGUAGE_USE[last_ind+1:]),) # Randomly choose language that wasn't chosen last.
    Languages_List += (lang,)
    last_lang = Languages_List[0] # First language.

    for cur_lang in Languages_List[1:]: # Iterate through language list, translating between each.
        if text[0] == ".": # Lingva has a problem with queries starting in periods. :(
            text = " " + text
        url = f"https://{random.choice(LINGVA_WEBSITES)}/api/v1/{last_lang}/{cur_lang}/{quote(text)}"

        if len(text) > DEFAULT_SPLIT_LENGTH or len(url) > 16331 or session == None: # Split text if it's too big.

            url_base_ind = url.rindex("/",0,52)+1

            url_base = url[:url_base_ind]
            url_query = url[url_base_ind:]
            query_length = len(url_query)
            max_length = 16331 - len(url_base)

            rind = ind = 0
            Translate_List = []
            Split_List = []
            while True:
                ind += max_length

                # Find the length of the text in utf-16 since Google Translate counts emoji's as multiple characters under this standard.
                while len(unquote(url_query[rind:ind]).encode('utf-16'))//2 > DEFAULT_SPLIT_LENGTH:
                    ind = ind-((ind-rind)//2)
                if ind >= query_length:
                    Translate_List += (url_base+url_query[rind:ind],)
                    Split_List += ('',)
                    break
                if url_query[ind] != "%":
                    ind -= 1
                    if url_query[ind] != "%":
                        ind -= 1
                if url_query[ind-3:ind] not in ("%20","%0A"):
                    if "%20" in url_query[rind:ind] or "%0A" in url_query[rind:ind]:
                        ind = rev_url_sp_nl.search(url_query[rind:ind]).end()+rind # Start of split.
                        next_ind = ind # End of split.
                        while url_query[next_ind:next_ind+3] in ("%20","%0A"):
                            next_ind += 3
                        while url_query[ind-3:ind] in ("%20","%0A"):
                            ind -= 3
                    else:
                        next_ind = ind
                else:
                    next_ind = ind
                    while url_query[next_ind:next_ind+3] in ("%20","%0A"):
                        next_ind += 3
                    while url_query[ind-3:ind] in ("%20","%0A"):
                        ind -= 3
                Translate_List += (url_base+url_query[rind:ind],)
                Split_List += (unquote(url_query[ind:next_ind]),)
                ind = rind = next_ind

            async with aiohttp.ClientSession() as sub_session: # Run asynchronous requests for each text piece in the list to speed up result retrieval.
                tasks = [asyncio.ensure_future(get_translation(sub_session, sub_url)) for sub_url in Translate_List]

                Results = await asyncio.gather(*tasks)

                text = ''.join([x for y in zip(Results, Split_List) for x in y]) # Result.

        else: # Text is translated normally.
            last_lang = cur_lang
            while True:
                try:
                    async with session.get(url) as response:
                        try:
                            text = (await response.json())['translation'].replace('/','⁄')
                            break
                        except Exception as e:
                            #url += '%2E'
                            print("Session Error", e)
                            time.sleep(1)
                except (aiohttp.ServerDisconnectedError, aiohttp.ClientResponseError, aiohttp.ClientConnectorError) as e:
                    print("Connection Error", e)
                    await asyncio.sleep(1)

        last_lang = cur_lang

    return pre_text+text+post_text

    
# Begins the obfuscation.
# Set variables related to measuring translation progress.
start_time = time.time()
counter = 0
FULL = 1
translating = True

itr = DEFAULT_ITERATIONS_VALUE # Amount of translations.

if DEFAULT_SPLIT_MODE == 0: # Initial Mode

    result = asyncio.run( obfuscate_length_split(inputText, itr, GOOGLE_LANGUAGE_ALL[GOOGLE_LANGUAGE_NAMES.index(DEFAULT_LANGUAGE)]) ) # Obfuscate Asynchronously

elif DEFAULT_SPLIT_MODE == 1: # Continuous Mode

    FULL = itr+1 # FULL is not set in the obfuscate function itself, so this must be set.
    result = asyncio.run( obfuscate(None, inputText, itr, GOOGLE_LANGUAGE_ALL[GOOGLE_LANGUAGE_NAMES.index(DEFAULT_LANGUAGE)]) ) # Obfuscate Asynchronously

else: # Newline Mode

    result = asyncio.run( obfuscate_newline_split(inputText, itr, GOOGLE_LANGUAGE_ALL[GOOGLE_LANGUAGE_NAMES.index(DEFAULT_LANGUAGE)]) ) # Obfuscate Asynchronously

outputText = result
# End progress estimation.
translating = False

timeString = str(time.time() - start_time)
print(timeString[0:(len(timeString.split(".")[0]) + 5)] + "... sec")

outputFile.write(outputText)