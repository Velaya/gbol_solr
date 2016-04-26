# -*- coding: UTF-8 -*-

###############################################
# getCommonNames.py
# Ver. 0.1.2
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
x_debug_results = 500


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

import json
from datetime import datetime
import requests
import MySQLdb



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
        db = MySQLdb.connect(host="144.76.31.113", user="koehler_zfmk", passwd="zfmk_bonn", db="koehler_zfmk")
        cur = db.cursor()
        sql_statement = 'SELECT DISTINCT canonicalName from identification'
        if debug:
            # in debug mode only some results
            sql_statement = '%s LIMIT %s' % (sql_statement, x_debug_results)
        cur.execute(sql_statement)
        for row in cur.fetchall():
            species_list.append(row[0])
    return species_list


def get_synonyms(species):
    """get date for a scientiffic name from openup.nhm-wien.ac.at as json
    Excample: http://openup.nhm-wien.ac.at/commonNames/?query={"type":"/name/common","query":"Turdus Merula"}"""
    url = 'http://openup.nhm-wien.ac.at/commonNames/?query={"type":"/name/common","query":"%s"}' % species
    json_data = requests.get(url).text
    if len(json_data) == 0:
        return None
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
    return entry.strip()


def get_available_languages():
    """Return a list auf available translation language.
       For debugging only! This doubles the load (and time) spent on the webservice).
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


def write_file_header(file_format, output_file):
    """Write a header for the output file. I only implemented the "solr synonym" so far"""

    # solr synonym file
    if file_format == 'solr synonym':
        comment_marker = '#'
    # all other formats
    else:
        comment_marker = '# //'

    output_file.write('%s Common Name Synonym List\n' % comment_marker)
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


def main():
    """Create a list of Common Names and write it to a text output_file"""

    species_list = get_species_list(source='db')

    # some output for the shell
    if debug:
        print '###########'
        print 'Debug Mode!'
        print '###########'
        print '%s species selected from data base:' % len(species_list)

    if debug:
        print
        print 'Preparing output file ... ',

    f = open(output_file_name, 'w', 1)
    if debug:
        print "openig file ..."
    write_file_header(output_format, f)
    if debug:
        print "writing header .... done!"
        print 'Starting to retrieve synonyms from webservice ...'
    for species in species_list:
        if species is not None and len(species) > 8:
            # some output for the shell
            if not debug:
                print species

            try:
                synonyms = get_synonyms(species)
                if debug:
                    print "%s retrieved from webservice: %s" % (species, synonyms)
            except:
                synonyms = ['# ERROR: unexpected result from get_synonyms for\t', species]

            try:
                # only append to list, if we have at least one synonym
                if synonyms and synonyms.find(',') > 0:
                    data = '%s\n' % synonyms.encode(encoding)
                    f.write(data)
            except:
                data = '# ERROR: Encoding Error: %s, %s\n' % (species, synonyms)
                f.write(data)
                if debug:
                    print '# ERROR: Encoding Error: %s, %s\n' % (species, synonyms)

    f.write('# Finished Processing:  Date: %s\n' % (datetime.now().strftime("%d/%m/%Y (%H:%M)")))
    f.write('######## E O F ##########')
    f.close()
    print
    print "### Done ###"

if __name__ == "__main__":
    main()
