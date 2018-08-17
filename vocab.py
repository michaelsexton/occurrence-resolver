import rdflib
import requests

sparql_query = '''PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
                 CONSTRUCT {{ ?u skos:prefLabel ?p }}
              '''

endpoint = 'http://vocabs.ands.org.au/repository/api/sparql/ga_commodity-code_v0-2'


def get_terms():
    response = requests.get(endpoint, params={"query": sparql_query})
    g = rdflib.Graph()
    g.parse(data=response.text, format='n3')

    terms = [str(term) for term in g.subjects()]
    return terms
