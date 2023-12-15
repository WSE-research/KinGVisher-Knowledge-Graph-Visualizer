import streamlit as st
from streamlit.components.v1 import html

from PIL import Image
import base64
import logging
import validators
import time
import os
import math
import random
from decouple import config
from util import include_css, download_image, save_uploaded_file, replace_values_in_index_html
import json
from SPARQLWrapper import SPARQLWrapper, JSON, POST
from pprint import pprint   
import streamlit as st
import streamlit.components.v1 as components  # Import Streamlit
import pandas as pd
from streamlit_agraph import agraph, Node, Edge, Config
from streamlit_tags import st_tags, st_tags_sidebar
import seaborn as sns

PAGE_ICON = config('PAGE_ICON')
PAGE_IMAGE = config('PAGE_IMAGE')
GITHUB_REPO = config('GITHUB_REPO')
DESCRIPTION = config('DESCRIPTION').replace("\\n", "\n") % (GITHUB_REPO, GITHUB_REPO + "/issues/new", GITHUB_REPO + "/issues/new")
META_DESCRIPTION = config('META_DESCRIPTION', default=None)
REPLACE_INDEX_HTML_CONTENT = config('REPLACE_INDEX_HTML_CONTENT', default=False, cast=bool)
CANONICAL_URL = config('CANONICAL_URL', default=None)
ADDITIONAL_HTML_HEAD_CONTENT = config('ADDITIONAL_HTML_HEAD_CONTENT', default="")

PAGE_TITLE = "Knowledge Graph Visualizer"
MIN_WIDTH = 10
MAX_WIDTH = 300
RENDER_SCALE_PIXELS = 8
DEFAULT_OUTPUT_WIDTH = 1024
BASIC_NODE_SIZE = 5
SLEEP_TIME = 0.1
START_RESOURCE_COLOR = "#0000FF"
NODE_COLOR_LITERAL = "#FFFF99"
NODE_COLOR_LABEL = "#CCFFCC"
LOCAL_CACHE_FOLDER = "local_cache/"

INGOING_EDGES_ONLY = "⭘ ⭢ ⬛: only ingoing edges to the start resources"
OUTGOING_EDGES_ONLY = "⭘ ⭠ ⬛: only outgoing edges from the start resources"
INGOING_AND_OUTGOING_EDGES = "⭘ ⮂ ⬛: include ingoing and outgoing edges"


DBPEDIA_ENDPOINT = "http://dbpedia.org/sparql"
WIKIDATA_ENDPOINT = "https://query.wikidata.org/sparql"

PREFIXES = {
    "dbr": "http://dbpedia.org/resource/",
    "dbo": "http://dbpedia.org/ontology/",
    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "owl": "http://www.w3.org/2002/07/owl#",
    "purl": "http://purl.org/dc/terms/",
    "schema": "http://schema.org/",
    "foaf": "http://xmlns.com/foaf/0.1/",
    "skos": "http://www.w3.org/2004/02/skos/core#",
    "xmls": "http://www.w3.org/2001/XMLSchema#",
    "wgs84_pos": "http://www.w3.org/2003/01/geo/wgs84_pos#",
    "prov": "http://www.w3.org/ns/prov#",
    "yago": "http://dbpedia.org/class/yago/",
    "dbp": "http://dbpedia.org/property/",
    "virtrdf": "http://www.openlinksw.com/schemas/virtrdf#",
    "virtrdf-data-formats": "http://www.openlinksw.com/virtrdf-data-formats#",
    "wd": "http://www.wikidata.org/entity/",
    "wds": "http://www.wikidata.org/entity/statement/",
    "wdv": "http://www.wikidata.org/value/>",
    "wdt": "http://www.wikidata.org/prop/direct/",
    "wikibase": "http://wikiba.se/ontology#",
    "p": "http://www.wikidata.org/prop/",
    "ps": "http://www.wikidata.org/prop/statement/",
    "pq": "http://www.wikidata.org/prop/qualifier/",
    "bd": "http://www.bigdata.com/rdf#",
    "oa": "http://www.w3.org/ns/openannotation/core/",
    "qa": "http://www.wdaqua.eu/qa#",
    "gold:hypernym": "http://purl.org/linguistics/gold/hypernym",
    "madsrdf": "http://loc.hi.hi.gov/hihi/",
    "bflc": "http://id.loc.gov/ontologies/bflc/",
    "ex": "http://example.org/",
    "gr": "http://purl.org/goodrelations/v1#",
    "spacerel": "http://data.ordnancesurvey.co.uk/ontology/spatialrelations/",
    "qb": "http://purl.org/linked-data/cube#"
}

width = 60
agree_on_showing_additional_information = True
render_scale_pixels = RENDER_SCALE_PIXELS
number_of_requests = 0
nodes = []
edges = []
palette = sns.color_palette().as_hex()
color_map = {}
blacklist_properties = []

logging.basicConfig()
logging.getLogger().setLevel(logging.INFO)


replace_values_in_index_html(st, REPLACE_INDEX_HTML_CONTENT, 
                             new_title=PAGE_TITLE, 
                             new_meta_description=META_DESCRIPTION, 
                             new_noscript_content=DESCRIPTION, 
                             canonical_url=CANONICAL_URL, 
                             page_icon_with_path=PAGE_ICON,
                             additional_html_head_content=ADDITIONAL_HTML_HEAD_CONTENT
                            )
st.set_page_config(layout="wide", initial_sidebar_state="expanded",
                   page_title=PAGE_TITLE,
                   page_icon=Image.open(PAGE_ICON)
                   )
include_css(st, [
            "css/style_github_ribbon.css",
            "css/style_menu_logo.css", 
            "css/style_logo.css", 
            "css/style_ascii_images.css", 
            "css/style_tabs.css", 
            "css/style_sttags.css"]
)  


with open(PAGE_IMAGE, "rb") as f:
    image_data = base64.b64encode(f.read()).decode("utf-8")
    st.sidebar.markdown(
        f"""
        <div style="display:table;margin-top:-10%;margin-bottom:15%;margin-left:auto;margin-right:auto;text-align:center">
            <a href="{GITHUB_REPO}" title="go to GitHub repository"><img src="data:image/png;base64,{image_data}" class="app_logo"></a>
        </div>
        """,
        unsafe_allow_html=True,
    )

sparql_endpoint = st.sidebar.text_input("SPARQL endpoint:", key="sparql_endpoint", value=DBPEDIA_ENDPOINT, help="SPARQL endpoint to query, e.g., %s or %s" % (DBPEDIA_ENDPOINT, WIKIDATA_ENDPOINT))

specific_graph = st.sidebar.text_input("Specific graph:", key="specific_graph", help="optional parameter")


if sparql_endpoint != None and validators.url(sparql_endpoint):
    sparql = SPARQLWrapper(sparql_endpoint)
    st.header(f"Knowledge Graph Visualizer for&nbsp;[{sparql_endpoint}]({sparql_endpoint}) ", help="Used prefixes: \n* " + "\n* ".join([f"`{prefix}: {prefix_url}`" for prefix, prefix_url in PREFIXES.items()]))
else:
    sparql = None
    st.header("Knowledge Graph Visualizer")
    st.info("Please provide a valid SPARQL endpoint, e.g., %s or %s" % (DBPEDIA_ENDPOINT, WIKIDATA_ENDPOINT))
    st.stop()

def execute_query_convert(sparql_endpoint, query_string):
    try:
        return query_execution_and_convert(sparql_endpoint, query_string)
    except Exception as e:
        logging.error(e)
        logging.error(query_string)
        st.error(st.code(query_string))
        st.error(e)
        return []

@st.cache_data(show_spinner="Fetching data from triplestore ...", ttl="7d")
def query_execution_and_convert(sparql_endpoint, query_string):
    logging.info("execute_query_convert_and_count on " + sparql_endpoint + ":" + query_string)
    sparql.setQuery(query_string)
    sparql.setReturnFormat(JSON)
    results = sparql.query().convert()
    return results["results"]["bindings"]
    

def get_graph_expression(graph):
    if graph != None and len(graph) > 0:
        return "GRAPH <%s> " % (graph,)
    else:
        return "GRAPH ?g "


def execute_start_resource_query_convert(sparql_endpoint, graph, all_start_values, p_values, p_blocked_values, limit, use_edges):
    
    
    size = 25
    start_values_chunks = [all_start_values[x:x+size] for x in range(0, len(all_start_values), size)]
    
    print("execute_start_resource_query_convert:" + str(len(all_start_values)) )
    pprint(start_values_chunks, width=160)
    
    if use_edges is INGOING_EDGES_ONLY or use_edges is INGOING_AND_OUTGOING_EDGES or use_edges is OUTGOING_EDGES_ONLY:
        pass # ok
    else:
        st.error("use_edges is not valid: " + str(use_edges))
    
    results = []
    all_queries = ""
    for start_values,count in zip(start_values_chunks, range(len(start_values_chunks))):
        
        start_values_sparql = " ".join(["<%s>" % x for x in start_values])
        
        if use_edges is INGOING_EDGES_ONLY or use_edges is INGOING_AND_OUTGOING_EDGES:
            query_string_ingoing = """
                    {   # ingoing
                        ?s ?p ?o .
                        # filter for start resources
                        VALUES ?o { %s }
                        BIND("ingoing" AS ?direction) # s should be used next
                    }
            """ % (start_values_sparql,)
        else:
            query_string_ingoing = ""
        
        if use_edges is OUTGOING_EDGES_ONLY or use_edges is INGOING_AND_OUTGOING_EDGES:
            query_string_outgoing = """
                    {   # outgoing
                        ?s ?p ?o .
                        # filter for start resources
                        VALUES ?s { %s }
                        BIND("outgoing" AS ?direction) # o should be used next
                    }
            """ % (start_values_sparql,)
        else:
            query_string_outgoing = ""
            
        if use_edges is INGOING_AND_OUTGOING_EDGES:
            query_string_ingoing += "\t\t\t\tUNION"
        
        # select all ingoing and outgoing resources of the start resources
        query_string = """
            PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            PREFIX dbr: <http://dbpedia.org/resource/>
            PREFIX dbo: <http://dbpedia.org/ontology/>
            
            SELECT ?s ?p ?o ?direction WHERE {
                %s {
                        %s
                        %s
                    
                    # define allowed types of p
                    %s 
                    
                    # define blocked types of p
                    %s
                }
            } 
            # LIMIT applied later
            # order results randomly
            ORDER BY RAND()
        """ % (get_graph_expression(graph), query_string_ingoing, query_string_outgoing, p_values, p_blocked_values)
        print("execute_start_resource_query_convert:", count, "/", len(start_values_chunks), query_string)
        
        all_queries += query_string
        results_iteration = execute_query_convert(sparql_endpoint, query_string)
        results += results_iteration
        
        # stop if we have enough results
        if len(results) >= limit:
            break
        else:
            time.sleep(SLEEP_TIME)

    return results, all_queries


def get_data(sparql_endpoint, number_of_results, allowed_properties, blocked_properties, start_resources, graph, use_edges):
    
    original_start_resources = start_resources.copy()
    
    p_values = " ".join(["<%s>" % x for x in allowed_properties])
    if len(allowed_properties) > 0:
        p_values = "VALUES ?p { %s }" % (p_values,)
    else:
        p_values = ""
        
    # filter out blocked properties
    p_blocked_values = "\n".join(["FILTER(STR(?p) != \"%s\")" % x for x in blocked_properties])
    
    # simple query to get all resources if no start resources are given
    if len(start_resources) == 0:
        query_string = """
            PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            PREFIX dbr: <http://dbpedia.org/resource/>
            PREFIX dbo: <http://dbpedia.org/ontology/>
            
            SELECT ?s ?p ?o 
            WHERE {
                %s {
                    ?s ?p ?o .
                    # define allowed types of p
                    %s 
                    # define blocked types of p
                    %s
                }
            } 
            LIMIT %d
        """ % (get_graph_expression(graph), p_values, p_blocked_values, number_of_results)
        
        with st.spinner('Wait for it...'):
            with st.expander("SPARQL query (LIMIT %d)" % (number_of_results,), expanded=False):
                st.code(query_string)

        return execute_query_convert(sparql_endpoint, query_string)

    else: # start resources are given
        all_query_strings = "" # save all queries for showing it in the expander
        results = [] # save all results
        # iterate over resources until we have enough results
        while number_of_results > len(results):
            results_iteration, query_string = execute_start_resource_query_convert(
                sparql_endpoint, 
                specific_graph, 
                start_resources, 
                p_values, 
                p_blocked_values, 
                number_of_results,
                use_edges=use_edges
            )

            all_query_strings += query_string
            new_start_resources = []
            
            # collect all ingoing and outgoing resources of the start resources
            try:
                for result in results_iteration:
                    s = result["s"]["value"]
                    o = result["o"]["value"]
                    direction = result["direction"]["value"]
                    if s not in start_resources and s not in new_start_resources and s not in start_resources and validators.url(s) and direction == "ingoing":
                        new_start_resources.append(s)
                    if o not in start_resources and o not in new_start_resources and o not in start_resources and validators.url(o) and direction == "outgoing":
                        new_start_resources.append(o) 
            except Exception as e:
                st.error(st.code(all_query_strings))
                st.error(e)
                logging.error(all_query_strings)
                logging.error(e)
                new_start_resources = []
                    
            print("STEP: old_start_resources:", len(start_resources), "results_iteration:", len(results_iteration), "results:", len(results))
            
            # while considering ingoing and outgoing edges, we want to ensure to expand
            if use_edges is INGOING_AND_OUTGOING_EDGES:
                start_resources = new_start_resources.copy()
            else: # otherwise we want to keep the original start resources to ensure we also expand more from the original start resources
                # be aware: this might lead to a situation, where we expand slower or even don't find the possible expansion due to the dominating original start resources
                start_resources =  start_resources.copy() + original_start_resources.copy()
            
            results += results_iteration
            print("STEP: new_start_resources:", len(new_start_resources), "results_iteration:", len(results_iteration), "results:", len(results))
            
            if len(new_start_resources) == 0: # stop if no more resources are found
                print("no more NEW start resources found")
                break
            else:
                time.sleep(SLEEP_TIME)

        with st.expander("SPARQL query (LIMIT %d by %d results for the start resources)" % (number_of_results, len(results)), expanded=False):
            st.code(all_query_strings)

        return results[:number_of_results]
        


def get_resources(sparql_endpoint, max):
        
        query_string = """
            PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            PREFIX dbr: <http://dbpedia.org/resource/>
            
            SELECT DISTINCT ?s WHERE {
                ?s ?p ?o .
            }
            LIMIT %d
        """ % (max,)
        results = execute_query_convert(sparql_endpoint, query_string)
        return [x["s"]["value"] for x in results]


def get_all_properties(sparql_endpoint, graph=None):
    
    cleaned_sparql_endpoint = sparql_endpoint.replace(":", "_").replace("/", "_").replace(".", "_")
    cache_filename= LOCAL_CACHE_FOLDER + "/all_properties_" + cleaned_sparql_endpoint + "_" + str(graph) + ".json"
    
    print("checking for cache file: " + cache_filename + " ...")
    if os.path.exists(cache_filename):    
        print("loading all properties from cache file: " + cache_filename + " ...")
        with open(cache_filename, "r") as f:
            all_properties = json.load(f)
            return all_properties        
    else:
        print("cache file not found, will create it later with the retrieved results: " + cache_filename + " ...")
    
    page = 0
    all_properties = []
    
    graph_expression = get_graph_expression(graph)
    
    while True:
        # will not work with more with properties that are not defined in the ontology, like rdf:type
        query_string = """
            PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>   
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            PREFIX dbr: <http://dbpedia.org/resource/>
            PREFIX dbo: <http://dbpedia.org/ontology/>
            PREFIX owl: <http://www.w3.org/2002/07/owl#>
            
            SELECT DISTINCT ?property WHERE {
                %s {
                    ?property rdf:type ?type .
                    VALUES ?type { rdf:Property owl:DatatypeProperty }
                }
            } 
            LIMIT 10000
            OFFSET %d
        """ % (graph_expression, page * 10000,)
        results = execute_query_convert(sparql_endpoint, query_string)
        
        if len(results) == 0:
            break
        else:
            all_properties += [x["property"]["value"] for x in results]
            page += 1
        
        
    # ask N times for properties that are not defined in the ontology, like rdf:type
    for i in range(2):
        query_string = """
            PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            PREFIX dbr: <http://dbpedia.org/resource/>
            PREFIX dbo: <http://dbpedia.org/ontology/>
            PREFIX owl: <http://www.w3.org/2002/07/owl#>
            PREFIX yago: <http://dbpedia.org/class/yago/>
            
            SELECT DISTINCT ?property WHERE {
                GRAPH ?g {
                    ?s ?property ?o .
                }
            }
            LIMIT 10000
        """
        results = execute_query_convert(sparql_endpoint, query_string)
        
        for result in results:
            p = result["property"]["value"]
            if p not in all_properties:
                #print("found new property: " + p)
                all_properties.append(p)
    
    # cache all data in a file
    with open(cache_filename, "w") as f:
        json.dump(all_properties, f)
        print("cache file written: " + cache_filename + " ...")
    
    return all_properties


def get_resource_data(sparql_endpoint, uri, graph):
    
    def replace_parenthesis(str):
        return str.replace("(", "\(").replace(")", "\)")
    
    if graph != None and len(graph) > 0:
        graph_expession = "GRAPH <%s> " % (graph,)
    else:
        graph_expession = "GRAPH ?g "
    
    if sparql_endpoint == WIKIDATA_ENDPOINT:
        query_string = """
            PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            PREFIX dbr: <http://dbpedia.org/resource/>
            
            SELECT DISTINCT ?p ?p_label ?o
            WHERE {
                %s {
                    <%s> ?p ?o .
                    FILTER(!isLiteral(?o) || lang(?o) = "" || langMatches(lang(?o), "EN"))
                    BIND(?p AS ?p_label)
                }
            }
            ORDER BY LCASE(?p_label)
        """ % (graph_expession, uri)
        
    else:
        query_string = """
            PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            PREFIX dbr: <http://dbpedia.org/resource/>
            
            SELECT DISTINCT ?p ?p_label ?o
            WHERE {
                %s {
                    <%s> ?p ?o .
                    ?p rdfs:label ?p_label .
                    FILTER(!isLiteral(?p_label) || lang(?p_label) = "" || langMatches(lang(?p_label), "EN"))
                    #BIND (datatype(?o) AS ?dt)
                    FILTER(STR(?p) != "http://dbpedia.org/ontology/wikiPageWikiLink")
                    FILTER(STR(?p) != "http://dbpedia.org/property/wikiPageUsesTemplate")
                    FILTER(STR(?p) != "http://www.w3.org/2002/07/owl#sameAs")
                    FILTER(!isLiteral(?o) || lang(?o) = "" || langMatches(lang(?o), "EN"))
                    #BIND(STR(?o) AS ?o_v)
                }
            }
            ORDER BY LCASE(?p_label)
        """ % (graph_expession,uri)
    #print(query_string)
    
    with st.expander("SPARQL query for " + uri.replace("_", "&#95;").replace(":", "\:"), expanded=False):
        st.code(query_string)
    
    results = execute_query_convert(sparql_endpoint, query_string)    
    return results


@st.cache_data
def get_dataframe_from_results(resource_data, indegree, outdegree):
    
    def get_property_urls(resource_data):
        for result in resource_data:
            p = result["p"]["value"]
            yield p

    def get_properties(resource_data):
        for result in resource_data:
            p = result["p"]["value"]
            p_label = result["p_label"]["value"]
            #yield "[%s](%s)" % (p_label, p)
            yield p_label
    
    def get_values(resource_data):
        for result in resource_data:
            o = result["o"]["value"]
            yield o
    
    df = pd.DataFrame({
        "property": ["indegree", "outdegree"] + list(get_properties(resource_data)),
        "property_url": ["", ""] + list(get_property_urls(resource_data)),
        "values": [indegree, outdegree] + list(get_values(resource_data))
    })

    return df


@st.cache_data(show_spinner="Fetching resource labels from triplestore ...")
def get_labels(sparql_endpoint, results, show_resource_labels):
    resources = []
    for result in results:
        s = result["s"]["value"]
        p = result["p"]["value"]
        o = result["o"]["value"]

        if validators.url(s) and s not in resources:
            resources.append(s)
        if validators.url(o) and o not in resources:
            resources.append(o)
        #if p not in resources:
        #    resources.append(p)

    # if no labels should be shown, return empty list for the labels
    if show_resource_labels is False:
        return [], resources

    size = 25
    resources_chunks = [resources[x:x+size] for x in range(0, len(resources), size)]

    results = []
    all_query_strings = ""
    for resources_chunk in resources_chunks:
        try:
            # special SPARQL query for Wikidata due to label service
            if sparql_endpoint == WIKIDATA_ENDPOINT:
                query_string = """ 
                    # wikidata needs a specific query for labels
                    SELECT ?s ?p (?sLabel AS ?o)
                    WHERE {
                        SELECT ?s ?p ?sLabel
                        WHERE 
                        {
                            GRAPH ?g {
                                BIND(?res AS ?s)
                                BIND(<http://www.w3.org/2000/01/rdf-schema#label> AS ?p)
                                BIND(?sLabel AS ?o)
                                
                                VALUES ?res { %s }
                                
                                {
                                    SERVICE wikibase:label { bd:serviceParam wikibase:language "en". } 
                                    #?prop wikibase:directClaim ?s .
                                }
                            }
                        }
                    }
                """ % (" ".join(["<%s>" % x for x in resources_chunk]))
                
            else:
                query_string = """
                    # get labels the standard way
                    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
                    PREFIX dbr: <http://dbpedia.org/resource/>
                    PREFIX dbo: <http://dbpedia.org/ontology/>
                    
                    SELECT ?s ?p ?o WHERE {
                        GRAPH ?g {
                            ?s ?p ?o .
                            VALUES ?s { %s }
                            VALUES ?p { rdfs:label }
                            FILTER ( LANG(?o) = "en" )
                        }
                    }
                """ % (" ".join(["<%s>" % x for x in resources_chunk]))

            results += execute_query_convert(sparql_endpoint, query_string)
            all_query_strings += query_string

        except Exception as e:
            st.error(st.code(all_query_strings))
            st.error(e)
    
    return results, resources


def replace_url_by_prefixes(url):
    for prefix, prefix_url in PREFIXES.items():
        if url.startswith(prefix_url):
            return prefix + ":" + url[len(prefix_url):]
    return url


def get_node_size(str):
    node_size = get_node_degree(str) + 1
    # make it proportionally smaller, use log scale
    return round(math.log(node_size * 20, 2))

@st.cache_data
def get_color(str):
    if str == "none":
        return "#000000"
    
    if str not in color_map and len(palette) > 0:
        last_color = palette.pop()
        color_map[str] = last_color
        return color_map[str]
    
    if str in color_map:
        return color_map[str]
    else:
        return "#666666"    

@st.cache_data
def get_node_color_palette(number_of_colors=40):
    # https://seaborn.pydata.org/tutorial/color_palettes.html#sequential-color-brewer-palettes
    node_color_palette = sns.color_palette("Blues", 40).as_hex() 
    # remove dark colors
    return node_color_palette[:round(0.66 * len(node_color_palette))]
    


@st.cache_data
def get_node_color(node_id, start_resources, p=None):
    
    if node_id in start_resources:
        return START_RESOURCE_COLOR
    
    # grey color of all labels
    if p != None and p in ["http://www.w3.org/2000/01/rdf-schema#label", "http://www.w3.org/2004/02/skos/core#prefLabel", "http://www.w3.org/2004/02/skos/core#altLabel"]:
        return NODE_COLOR_LABEL
    
    if node_id == "none":
        return "#000000"
    
    if validators.url(node_id) == True:
        node_degree = get_node_degree(node_id)
        max_degree = get_max_node_degree()
        
        global node_color_palette # TODO: move to class property
        i = min(round(node_degree / max_degree * (len(node_color_palette) - 1)), (len(node_color_palette) - 1))
        color = node_color_palette[i]
        return color
    else: # literal
        return NODE_COLOR_LITERAL


def get_font_values(s, start_resources, p):
    if s in start_resources:
        return {
            "color": "#FFFFFF",
            "size": node_font_size + 2
        }
    elif p != None and p in ["http://www.w3.org/2000/01/rdf-schema#label", "http://www.w3.org/2004/02/skos/core#prefLabel", "http://www.w3.org/2004/02/skos/core#altLabel"]:
        return {
            "color": "#000000"
        }
    else:
        return {} # use default values

def get_max_node_degree():
    return max(max(indegree_map.values()), max(outdegree_map.values()))

def get_node_degree(str):
    if str in indegree_map and str in outdegree_map:
        return indegree_map[str] + outdegree_map[str]
    elif str in indegree_map:
        return indegree_map[str]
    elif str in outdegree_map:
        return outdegree_map[str]
    else:
        return 0 # should never happen

def create_help_string_from_list(my_values):
    my_values_copy = my_values.copy()
    random.shuffle(my_values_copy)
    return "Examples: \n* `" + "`\n* `".join(my_values_copy[:25]) + "`"

node_color_palette = get_node_color_palette()

all_properties = get_all_properties(sparql_endpoint, graph=specific_graph)

all_properties_copy = all_properties.copy()
random.shuffle(all_properties_copy)
st.markdown("""
            <span class="properties_whitelist">Properties whitelist:</span> 
            What properties should be shown (%d available)?""" 
            % (len(all_properties),), help=create_help_string_from_list(all_properties_copy), unsafe_allow_html=True)
whitelist_properties = st_tags(
    key="whitelist_properties",
    label="",
    text='Type here',
    suggestions=all_properties,
    maxtags=-1,
)


st.markdown("""
            <span class="properties_blacklist">Properties blacklist:</span> 
            What properties should *NOT* be shown (%d available)?""" 
            % (len(all_properties),), help=create_help_string_from_list(all_properties_copy), unsafe_allow_html=True)
blacklist_properties = st_tags(
    key="blacklist_properties",
    label="",
    text='Type here',
    suggestions=all_properties,
    maxtags=-1,
    value=blacklist_properties
)


#start_resources = st.multiselect("What resources should be shown?", get_resources(max=10000))


known_available_resources = get_resources(sparql_endpoint, max=10000)
if len(known_available_resources) == 10000:
    known_available_resources_text = "more than 10000"
else:
    known_available_resources_text = str(len(known_available_resources))
    
st.markdown("""
            <span class="start_resources">What resources (of %s) should be used for the start (will search for properties from these nodes)?</span>""" 
            % (known_available_resources_text, ), help=create_help_string_from_list(known_available_resources), unsafe_allow_html=True)
start_resources = st_tags(
    key="start_resources",
    label="",
    text='Type here',
    suggestions=known_available_resources,
    maxtags=-1    
)

# only if start resources are available, we can decide to use ingoing and outgoing edges or not
if len(start_resources) > 0:
    use_edges_options = [INGOING_AND_OUTGOING_EDGES, INGOING_EDGES_ONLY, OUTGOING_EDGES_ONLY]
    use_edges = st.selectbox("Filter type of edges: ", use_edges_options, index=0)
else:
    use_edges = INGOING_AND_OUTGOING_EDGES


number_of_results = st.sidebar.slider("number of edges",min_value=10, max_value=1000, value=10, step=10)
if number_of_results >= 300:
    st.sidebar.info("Please be patient, this might take a while depending on your browser's computing power.")
    
shape = st.sidebar.selectbox('shape',['box','ellipse','text','dot','square','star','triangle','triangleDown'], index=0) # ,'circle','database','image','circularImage','diamond','hexagon'
show_resource_labels = st.sidebar.checkbox("show resource labels", value=True)
node_font_size = st.sidebar.slider("node font size",min_value=1, max_value=20, value=8)
edge_font_size = st.sidebar.slider("edge font size",min_value=1, max_value=20, value=8)
layout = "" # st.sidebar.selectbox('layout',['dot','neato','circo','fdp','sfdp'], index=0)
rankdir = "" # st.sidebar.selectbox("rankdir", ['BT', 'TB', 'LR', 'RL'], index=2)
ranksep = "" # st.sidebar.slider("ranksep",min_value=0, max_value=20, value=10)
nodesep = "" # st.sidebar.slider("nodesep",min_value=0, max_value=20, value=5)
nodeSpacing = "" # st.sidebar.slider("nodeSpacing",min_value=50, max_value=500, value=200, step=50)
springLength = st.sidebar.slider("edge length",min_value=0, max_value=500, value=150)
# stabilization = True
fit = True
edgeMinimization = False
# solver = st.sidebar.selectbox("solver", ['barnesHut', 'repulsion', 'hierarchicalRepulsion', 'forceAtlas2Based'], index=2)

hierarchical = st.sidebar.checkbox("hierarchical layout", value=False)

show_visualization_options_in_rendered_network = st.sidebar.checkbox("Show visualization options in rendered network", value=False)

st.sidebar.markdown("----")
st.sidebar.info("The app will cache the SPARQL query results for 7 days to not waste resources of the used SPARQL endpoint.")
if st.sidebar.button("Clear all cached entries"):
    # Clear values from *all* all in-memory and on-disk data caches:
    # i.e. clear values from both square and cube
    st.cache_data.clear()

data = get_data(
    sparql_endpoint, 
    number_of_results=number_of_results, 
    allowed_properties=whitelist_properties, 
    blocked_properties=blacklist_properties, 
    start_resources=start_resources, 
    graph=specific_graph,
    use_edges=use_edges
)
labels, resources = get_labels(sparql_endpoint, data, show_resource_labels)
indegree_map = {}
outdegree_map = {}
property_counter_map = {}
for result in data:
    s = result["s"]["value"]
    p = result["p"]["value"]
    o = result["o"]["value"]
    
    if s not in outdegree_map:
        outdegree_map[s] = 0
    outdegree_map[s] += 1
    
    if o not in indegree_map:
        indegree_map[o] = 0
    indegree_map[o] += 1

    # count number of properties
    if p not in property_counter_map:
        property_counter_map[p] = 0
    property_counter_map[p] += 1

with st.expander("Number of **nodes: %d**, number of **properties: %d**" % (len(property_counter_map),len(resources)), expanded=False):
    properties_df = pd.DataFrame({
        "property": list(property_counter_map.keys()),
        "count": list(property_counter_map.values())
    }).sort_values(by="count", ascending=False)
    st.dataframe(properties_df)
    # filter_properties_buttons = [False for i in range(len(properties_df))]
    # for i in range(len(properties_df)):
    #     print(properties_df.loc[i, "property"], properties_df.loc[i, "count"])
    #     filter_properties_buttons[i] = st.button("%s (%d)" % (properties_df.loc[i, "property"], properties_df.loc[i, "count"]), help="add this property to the blacklist", key=properties_df.loc[i, "property"])
    #st.toast("""You might use these properties for the whitelist or blacklist.""", icon="💡", )

# add all properties that were clicked to the blacklist
# blacklist_properties += [properties_df.loc[i, "property"] for i in range(len(properties_df)) if filter_properties_buttons[i] == True] 


for result in data + labels:
    # https://github.com/ChrisDelClea/streamlit-agraph/blob/master/streamlit_agraph/node.py#L18
    
    s = result["s"]["value"]
    s_shape = shape
    if "s_type" in result:
        s_type = replace_url_by_prefixes(result["s_type"]["value"])
    else:
        s_type = "none"
        
    p = result["p"]["value"]
    
    o = result["o"]["value"]
    if validators.url(o):
        o_label = replace_url_by_prefixes(o)
    else:
        o_label = o[:64] # cut down to 64 characters

    o_shape = shape
    if "o_type" in result:
        o_type = replace_url_by_prefixes(result["o_type"]["value"])
    else:
        o_type = "none"

    if o in start_resources:
        o_shape = "box"
    if s in start_resources:
        s_shape = "box"
    
    if p in ["http://www.w3.org/2000/01/rdf-schema#label", "http://www.w3.org/2004/02/skos/core#prefLabel", "http://www.w3.org/2004/02/skos/core#altLabel"]:
        length = round(0.66 * springLength)
    else:
        length = springLength
    
    
    if s not in [x.id for x in nodes]:
        nodes.append( Node(id=s, label=replace_url_by_prefixes(s), size=get_node_size(s), font=get_font_values(s, start_resources, p), color=get_node_color(s, start_resources), shape=s_shape) )
    if o not in [x.id for x in nodes]:
        nodes.append( Node(id=o, label=o_label, size=get_node_size(o), font=get_font_values(o, start_resources, p), color=get_node_color(o, start_resources, p), shape=o_shape ) )
    edges.append( Edge(source=s, label=replace_url_by_prefixes(p), target=o, color=get_color(p), length=length, arrows_to=True, arrows_from=False, type="CURVE_SMOOTH") )




# https://github.com/ChrisDelClea/streamlit-agraph/blob/master/streamlit_agraph/config.py
config = Config(width="100%",
                height=800,
                autoResize=True,
                groups={}, # dict of node groups (refer to https://visjs.github.io/vis-network/docs/network/)
                directed=True, 
                configure={
                    "enabled": show_visualization_options_in_rendered_network,
                    "showButton": True, 
                    "filter": True 
                },
                edges={ 
                    "font": {
                        "size": edge_font_size,
                        "strokeWidth": 1
                    },      
                },
                nodes={
                    "font": {
                        "size": node_font_size,
                    }
                },                
                layout={
                    "hierarchical": {
                        "enabled": hierarchical,
                        "shakeTowards": "roots"
                    }
                },                
                # physics={
                #     "enabled": {
                #         "solver": solver,
                #         "barnesHut": {
                #             "centralGravity": 0.0,
                #             "springLength": springLength,
                #             "springConstant": 0.01,
                #             "damping": 0.09,
                #             "avoidOverlap": 0.0
                #         },
                #         "repulsion": {
                #             "centralGravity": 0.0,
                #             "springLength": springLength,
                #             "springConstant": 0.01,
                #             "nodeDistance": 100,
                #             "damping": 0.09
                #         },
                #         "hierarchicalRepulsion": {
                #             "centralGravity": 0.0,
                #             "springLength": springLength,
                #             "springConstant": 0.01,
                #             "nodeDistance": 100,
                #             "damping": 0.09
                #         },
                #         "forceAtlas2Based": {
                #             "gravitationalConstant": -50,
                #             "centralGravity": 0.01,
                #             "springLength": springLength,
                #             "springConstant": 0.08,
                #             "damping": 0.4,
                #             "avoidOverlap": 0.0
                #         },
                #         "maxVelocity": 100,
                #         "minVelocity": 1
                #     }
                # },
                #     "stabilization": stabilization
                #},
                # graphviz_layout=layout,
                # graphviz_config={
                #     "rankdir": rankdir, 
                #     "ranksep": ranksep, 
                #     "nodesep": nodesep
                # },
                #stabilization=stabilization,
                #fit=fit,
                #edgeMinimization=edgeMinimization,
                #nodeSpacing=nodeSpacing,
                #node={'labelProperty':'label'},
                #hierarchical=False,
                #collapsible=True,
                # **kwargs
                )

return_value = agraph(nodes=nodes, edges=edges, config=config)

#st.sidebar.markdown("### Number of executed query for the current visualization: %d" % (number_of_requests,))

if return_value is not None:    
    try:    
        if validators.url(return_value):
            resource_data = get_resource_data(sparql_endpoint, return_value, specific_graph)
        
            properties_df = get_dataframe_from_results(resource_data, indegree=indegree_map.get(return_value,0), outdegree=outdegree_map.get(return_value,0))
            st.dataframe(properties_df,
                        column_config={
                            "property": st.column_config.TextColumn(),
                            "property_url": st.column_config.LinkColumn(),
                        },
                        width=1000,
                        height=500,
            )
        else:
            st.info("Please click on a resource node to see more information from the knowledge graph.")
    except Exception as e:
        st.error(e)



st.markdown("""
---
Brought to you by the [<img style="height:3ex;border:0" src="https://avatars.githubusercontent.com/u/120292474?s=96&v=4"> WSE research group](https://wse-research.org/) at the [Leipzig University of Applied Sciences](https://www.htwk-leipzig.de/).

See our [GitHub team page](http://wse.technology/) for more projects and tools.
""", unsafe_allow_html=True)

with open("js/change_menu.js", "r") as f:
    javascript = f.read()
    components.html(f"<script style='display:none'>{javascript}</script>")

components.html("""
<script>
github_ribbon = parent.window.document.createElement("div");            
github_ribbon.innerHTML = '<a id="github-fork-ribbon" class="github-fork-ribbon right-bottom" href="%s" target="_blank" data-ribbon="Fork me on GitHub" title="Fork me on GitHub">Fork me on GitHub</a>';
if (parent.window.document.getElementById("github-fork-ribbon") == null) {
    parent.window.document.body.appendChild(github_ribbon.firstChild);
}
</script>
""" % (GITHUB_REPO,))
