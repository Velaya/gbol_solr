# -*- coding: UTF-8 -*-

###############################################
# getCommonNames_multithreading.py
# Ver. 0.2 (multithreading support)
# Script to retrieve common names from Rest-API
# http://openup.nhm-wien.ac.at/commonNames/
# of Uni Wien (Heimo Reiner)
# Christian Koehler, ZFMK: c.koehler@zfmk.de
###############################################

###############################################
# some definitions
###############################################

# debug mode (restrict number of results to x_debug_results, give additional info). Slower!
debug = False
x_debug_results = 100

# database connection:
db_host = "144.76.31.113"
db_user = "koehler_zfmk"
db_passwd = "zfmk_bonn"
db_db = "koehler_zfmk"

# number of worker threads to complete the processing. Value between 50 and 100 is recommended.
num_worker_threads = 190

# output file name
output_file_name = 'Synonyms_common_names.txt'

# Encoding for output file
encoding = "UTF-8"

# Output format. So far we only have 'solr synonym'
# I will add additional formats on request
output_format = 'solr synonym'

# List of wanted languages. Note: Webservice does not always use ISO country codes
# The webservice provides the following languages:
# None, Ain, Bokm\xe5l, Chi, Cze, Dut, Dutch, Dzo, Eng, English, Fre, French, Ger, German, Gre, Hin, Hindi, Hrv, Srp,
# Hun, Ita, Jpn (Kanji), Jpn (Katakana), Kas, Kas, Pan, Kor (Hangul), Mon, Nep, Nep (uncertain), Nor, Nynorsk, Pahari?,
# Pan, Pol, Por, Rus, Russian, Sinhala, Slo, Spa, Spainsh, Spanish, Srp, Swe, Tamil, Tuk, Tur, Urd, ces, dan, en, e,
# fas, fi, gl, heb, hocg, ir, mi, nld, rus, slk, sv, swe, uk, ukr, we
# Use "all" to get all languages
# example: languages = 'all'
languages = ['German', 'Ger', 'de', 'en', 'eng', 'English', 'Eng']

# END OF DEFINITIONS ############################

import Queue
import threading
import json
from datetime import datetime
from time import sleep
from random import randint
import requests
import MySQLdb

# input queue with all species
species_queue = Queue.Queue(maxsize=0)

# output queue with the retrieved synonyms
synonym_queue = Queue.Queue(maxsize=0)


def get_species_list(source='buildin'):
    """Get a list of species.
       Data can be retrieved from database (source=db) or as an example list (source=buildin)"""

    # Fixed list of some random species for testing without db connection
    species_list = ['Turdus merula', ' Salix alba', 'Russula violacea', 'Russula violeipes', 'Russula virescens ',
                    'Russula viscida ', 'Russula xerampelina ', 'Russula zvarae ',
                    'Ruta angustifolia ', 'Ruta chalepensis ', 'Ruta fruticulosa ', 'Ruta graveolens ',
                    'Ruta linifolia ', 'Ruta montana ', 'Ruta patavina ', 'Ruta pinnata ', 'Ruta pubescens ',
                    'Ruthalicia eglandulosa ', 'Rutidea decorticata ', 'Rutidea smithii ', 'Rutilaria ',
                    'Rutilaria edentula ', 'Rutilaria epsilon longicornis', 'Schiedea obovata', 'Schiedea perlmanii',
                    'Schiedea sarmentosa', 'Schiekia orinocensis', 'Scabiosa africana', 'Scabiosa agrestis',
                    'Scabiosa albanensis', 'Scabiosa albescen', 'Scabiosa albocincta', 'Scabiosa alpina',
                    'Scabiosa altissima', 'Scabiosa argentea', 'Scabiosa arvensis', 'Scabiosa atropurpurea',
                    'Scabiosa attenuata', 'Scabiosa australis', 'Scariola alpestris', 'Salvia africana',
                    'Salvia discolor', 'Sanguisorba alpina']

    if source == 'db':
        species_list = []
        db = MySQLdb.connect(host=db_host, user=db_user, passwd=db_passwd, db=db_db)
        cur = db.cursor()
        sql_statement = 'SELECT DISTINCT taxonAtomised.canonical FROM taxonAtomised'
        if debug:
            # in debug mode only some results
            sql_statement = '%s LIMIT %s' % (sql_statement, x_debug_results)
        cur.execute(sql_statement)
        for row in cur.fetchall():
            species_list.append(row[0])
    return species_list


def get_synonym(species):
    """Look up the synonym for a species from the web service"""
    # give the webservice a break :-)
    sleep(randint(2, 6))
    url = 'http://openup.nhm-wien.ac.at/commonNames/?query={"type":"/name/common","query":"%s"}' % species
    json_data = requests.get(url).text
    if len(json_data) < 20 or "result" not in json.loads(json_data):
        # an 'empty' response may contain something like  {u'result': []}
        return None
    if len(json_data) > 20 and "result" not in json.loads(json_data):
        # trying to identify broken responeses
        print "ERROR in get_sysnonym: length: %s JSON %s returned %s" % (species, len(json_data), json.loads(json_data))
    results = json.loads(json_data)['result']
    common_name_dict = {}
    for i in results:
        if languages == 'all' or i['language'] in languages:
            # only exact matches marked with "match" (webservice provides fuzzy search, too)
            if i['match']:
                if i['language'] not in common_name_dict.keys():
                    common_name_dict[i['language']] = []
                if i['name'] not in common_name_dict[i['language']]:
                    common_name_dict[i['language']].append(i['name'])
    entry = ''
    for language in common_name_dict.keys():
        for synonym in common_name_dict[language]:
            # add new synonym, if it does not contain a comma (like 'Melon, Water')
            if synonym not in entry and synonym.find(',') == -1:
                # clean up a bit (get rid of commas, strip trailing spaces, remove double spaces)
                entry = '%s %s,' % (entry, synonym.strip().replace('  ', ' '))
        # append scientific name at the end (solr synonym style)
        entry = ('%s %s' % (entry, species))

        species_to_go = species_queue.qsize()
        print "Found for %s: %s \t\t (%s to go)" % (species, entry, species_to_go,)

    return entry.strip()


def get_available_languages():
    """Return a list of available translation language of the webservice.
       For debugging only! This takes some time ... be patient.
       In debug mode only some species (x_debug_results) are inspected."""
    language_list = []
    species_list = get_species_list(source='db')
    if debug:
        print species_list
        number_of_species = len(species_list)
        print '%s species in list' % number_of_species
        print 'Inspecting ... starting count down: ',
    for species in species_list:
        if debug:
            number_of_species -= 1
            print ('%s ... ' % number_of_species),
        # sometimes we have invalid species names (None, empty string) in DB
        if species:
            url = 'http://openup.nhm-wien.ac.at/commonNames/?query={"type":"/name/common","query":"%s"}' % species
            json_data = requests.get(url).text
            results = json.loads(json_data)['result']
            for i in results:
                if i and i['language'] not in language_list:
                    language_list.append(i['language'])
    return sorted(language_list)


# another queued thread we will use to print output
def file_writer():
    """Asynchron writing synonyms to file from queue.
    Note: the functions does not implement semaphores or other file locking. So it is not thread safe (yet).
    Multiple threads for writing to file does not make sense here, as this task is 1000 times faster than
    the data retrieval from the REST api"""
    while True:
        # when the worker puts stuff in the output queue, write them to the file system
        synonyms = synonym_queue.get()
        output_file = open(output_file_name, 'a', 1)
        try:
            # only append to list, if we have at least one synonym
            if synonyms and synonyms.find(',') > 0:
                data = '%s\n' % synonyms.encode(encoding)
                output_file.write(data)
                if debug:
                    print 'Writing: %s \t(%s in queue)' % (synonyms, synonym_queue.qsize())
        except:
            data = '# ERROR: Encoding Error: %s\n' % synonyms
            output_file.write(data)
            if debug:
                print data
        output_file.close()
        synonym_queue.task_done()


def write_file_header(file_format):
    """Write a header for the output file. I only implemented the "solr synonym" so far"""

    output_file = open(output_file_name, 'w', 1)
    # solr synonym file
    if file_format == 'solr synonym':
        comment_marker = '#'
    # all other formats
    else:
        comment_marker = '# //'

    output_file.write('%s Common Name Synonym List\n' % comment_marker)
    output_file.write('%s Version 0.2 mt\n' % comment_marker)
    output_file.write('%s Format: %s\n' % (comment_marker, file_format))
    output_file.write('%s Languages: %s\n' % (comment_marker, languages))
    if debug:
        output_file.write('%s Available Languages: %s\n' % (comment_marker, get_available_languages()))
    output_file.write('%s Encoding: %s\n' % (comment_marker, encoding))
    output_file.write('%s Date: %s\n' % (comment_marker, datetime.now().strftime("%d/%m/%Y (%H:%M)")))
    output_file.write('%s Christian Koehler (koehler@zfmk.de)\n' % comment_marker)
    if debug:
        output_file.write('%s Debug mode!)\n' % comment_marker)

    output_file.write('\n')
    output_file.close()


def worker():
    """Process that each worker thread will execute until the species_queue is empty"""
    while True:
        # get item from queue, do work on it, let queue know processing is done for one item
        item = species_queue.get()
        synonym_queue.put(get_synonym(item))
        species_queue.task_done()


# launch all of our queued processes
def main():
    # prepare the output file
    write_file_header(output_format)

    # Launches a number of worker threads to perform operations using the queue of inputs
    for i in range(num_worker_threads):
        t = threading.Thread(target=worker)
        t.daemon = True
        t.start()

    # launches a single "printer" thread to output the result (makes things neater)
    t = threading.Thread(target=file_writer)
    t.daemon = True
    t.start()

    # populate species_queue
    species_list = get_species_list('db')
    for species in species_list:
        # there are some empty or broken enties
        if species is not None and len(species) > 6:
            species_queue.put(species)

    # wait for the two queues to be emptied (and workers to close)
    species_queue.join()  # block until all tasks are done
    print "Got all data from REST api"
    synonym_queue.join()

    # Some info at the end
    output_file = open(output_file_name, 'a', 1)
    output_file.write('# Finished Processing:  Date: %s\n' % (datetime.now().strftime("%d/%m/%Y (%H:%M)")))
    output_file.write('######## E O F ##########')
    output_file.close()

    print "Processing and writing complete"


main()
