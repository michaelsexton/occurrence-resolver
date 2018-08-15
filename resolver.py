import requests
from xml.etree import ElementTree

class OccurrenceResolver:

  ns = {'mo' : 'http://xmlns.geoscience.gov.au/minoccml/1.0'}

  parameters = {
    'service': 'WFS',
    'version' : '1.1.0',
    'request' : 'GetFeature',
    'maxFeatures' : 50
  }

  feature_types = {'mo:MinOccView' : {
            'name' : 'mo:name',
            'shape' : 'mo:shape/gml:Point/gml:pos',
            'spec_uri' : 'mo:earthResourceSpecification_uri'
        }, 'erl:MineralOccurrenceView' : {
            'name' : 'erl:name',
            'shape' : 'erl:shape/gml:Point/gml:pos',
            'spec_uri' : 'erl:specification_uri'
        }}

  def __init__(self, state, endpoint, feature_type, lite_version=1, er_version=1):
    self.endpoint = endpoint
    self.state = state
    self.feature_type = feature_type
    self.lite_version = lite_version
    self.er_version = er_version
    self.set_namespace()

  def set_namespace(self):
    if self.lite_version == 1:
      self.ns['erl'] = 'http://xmlns.earthresourceml.org/earthresourceml-lite/1.0'
      self.ns['wfs'] = 'http://www.opengis.net/wfs'
      self.ns['gml'] = 'http://www.opengis.net/gml'
      self.parameters['outputFormat'] = 'gml3'
    elif self.lite_version == 2:
      self.ns['erl'] = 'http://xmlns.earthresourceml.org/earthresourceml-lite/2.0'
      self.ns['wfs'] = 'http://www.opengis.net/wfs/2.0'
      self.ns['gml'] = 'http://www.opengis.net/gml/3.2'
      self.parameters['outputFormat'] = 'gml32'
    if self.er_version == 1:
      self.ns['er'] = 'urn:cgi:xmlns:GGIC:EarthResource:1.1'
    elif self.er_version == 2:
      self.ns['er'] = 'http://xmlns.earthresourceml.org/EarthResource/2.0'

  def process_endpoints(self):

    self.parameters['typeName'] = self.feature_type
    response=requests.get(self.endpoint, params=self.parameters)
    
    print(response.url)
    root = ElementTree.fromstring(response.text)
    occurrences_path = "gml:featureMembers/" + self.feature_type
    features = root.findall('gml:featureMembers', self.ns) or root.findall('gml:featureMember', self.ns) or root.findall('wfs:member', self.ns)
    self.process_features(features)

  def process_features(self, features):
    for feature in features:
        occurrences = feature.findall(self.feature_type, self.ns)
        self.process_occurrences(occurrences)

  def process_occurrences(self, occurrences):
    path_map = self.feature_types[self.feature_type]
    for occurrence in occurrences:
      name_path = path_map['name']
      spec_path = path_map['spec_uri']
      shape_path = path_map['shape']
      otherid = self.get_id(occurrence.attrib)
      name = occurrence.find(name_path,self.ns).text
      latlng = occurrence.find(shape_path,self.ns)
        
      specification_uri = occurrence.find(spec_path, self.ns).text
      if latlng is not None:
        latitude, longitude = [float(pos) for pos in latlng.text.split(' ')]
      else:
        latitude = None
        longitude = None
      commods = self.process_specification(specification_uri)
      print(otherid, name, latitude, longitude, commods)

  def get_id(self,attrib):
    if '{http://www.opengis.net/gml}id' in attrib:
      gml_id = attrib['{http://www.opengis.net/gml}id']
    elif 'id' in attrib:
      gml_id = attrib['id']
    else:
      return None
    return gml_id.split('.')[-1]

  def process_specification(self, uri):
    response = self.get_feature(uri)
    root = ElementTree.fromstring(response.text)
    names_nodes = root.findall('.//er:MineralOccurrence/gml:name', self.ns)
    names = self.process_names(names_nodes)
    commodity_nodes = root.findall('.//er:MineralOccurrence/er:commodityDescription/er:Commodity',self.ns)
    commodities = self.process_commodities(commodity_nodes)
    return [names, commodities]

  def process_names(self,names_nodes):
    return [name.text for name in names_nodes if ('codeSpace' in name.attrib and name.attrib['codeSpace'] not in ['http://www.ietf.org/rfc/rfc2616','http://www.ietf.org/rfc/rfc2141'])]
      



  def process_commodities(self, commodity_nodes):
    commods = []
    order = 1
    for node in commodity_nodes:
      commod = node.find('er:commodity', self.ns)
      commodname = node.find('er:commodityName',self.ns)
      if commod is not None:
        code = commod.attrib['{http://www.w3.org/1999/xlink}href']
      elif commodname is not None:
        code = commodname.text.replace('urn:cgi:classifier:GA:commodity:','')
      else:
        code = None
      order = node.find('er:commodityRank',self.ns)

      importance = node.find('er:commodityImportance', self.ns)
      if order is not None:
        order = int(order.text)
      if importance is not None:
        importance = importance.text
      commods.append((code,order,importance))
    return commods

  def get_feature(self, uri):
    response = requests.get(uri)
    if response.status_code == 200:
      return response
    feature_id = 'er.'+'.'.join(uri.split('/')[-2:])
    if self.state == 'sa':
      feature_id = feature_id + 'deposit'
    parameters = {'service': 'WFS',
              'version' : '1.1.0',
              'request' : 'GetFeature',
              'typeName' : 'er:MineralOccurrence',
              'featureId' : feature_id}
    return requests.get(self.endpoint, params=parameters)
