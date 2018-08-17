import requests
import logger
import vocab
import db

from xml.etree import ElementTree


class OccurrenceResolver:
    ns = {'mo': 'http://xmlns.geoscience.gov.au/minoccml/1.0'}

    max_features = 10

    parameters = {
        'service': 'WFS',
        'version': '1.1.0',
        'request': 'GetFeature',
        'maxFeatures': max_features
    }

    feature_types = {'mo:MinOccView': {
        'name': 'mo:name',
        'shape': 'mo:shape/gml:Point/gml:pos',
        'spec_uri': 'mo:earthResourceSpecification_uri'
    }, 'erl:MineralOccurrenceView': {
        'name': 'erl:name',
        'shape': 'erl:shape/gml:Point/gml:pos',
        'spec_uri': 'erl:specification_uri',
        'commodity_uri': 'erl:representativeCommodity_uri'
    }}

    def __init__(self, state, endpoint, feature_type, lite_version=1, er_version=1):
        logger.log("Inititalising Occurrence Resolver for state {0} ({1})".format(state.upper(), endpoint))
        self.endpoint = endpoint
        self.state = state
        self.feature_type = feature_type
        self.lite_version = lite_version
        self.er_version = er_version
        self.set_namespace()
        # self.total = 10
        self.commodity_terms = vocab.get_terms()
        self.commodity_lookup = db.get_commodities()
        self.total = self.get_total()

    def get_total(self):
        logger.log('Querying service to determine feature count ...')
        parameters = {
            'service': 'WFS',
            'version': '1.1.0',
            'request': 'GetFeature',
            'typeName': self.feature_type,
            'resultType': 'hits'
        }
        response = requests.get(self.endpoint, params=parameters)
        root = ElementTree.fromstring(response.text)
        num_features = int(root.attrib['numberOfFeatures'])
        logger.log('Number of features for {0}: {1}'.format(self.state, num_features))
        return num_features

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
        start_index = 0
        while start_index < self.total:
            self.parameters['startIndex'] = start_index
            self.parameters['typeName'] = self.feature_type
            response = requests.get(self.endpoint, params=self.parameters)
            root = ElementTree.fromstring(response.text)
            occurrences_path = "gml:featureMembers/" + self.feature_type
            features = root.findall('gml:featureMembers', self.ns) or root.findall('gml:featureMember',
                                                                                   self.ns) or root.findall(
                'wfs:member', self.ns)
            self.process_features(features)
            start_index = start_index + self.max_features

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

            if self.feature_type == 'erl:MineralOccurrenceView':
                self.check_representative_commodity(occurrence)

            otherid = self.get_id(occurrence.attrib)
            name = occurrence.find(name_path, self.ns).text
            latlng = occurrence.find(shape_path, self.ns)

            specification_uri = occurrence.find(spec_path, self.ns).text

            if latlng is not None:
                latitude, longitude = [float(pos) for pos in latlng.text.split(' ')]
            else:
                latitude, longitude = None, None
                logger.log("No geometry found for this occurrence", logger.WARNING)

            names, commodities = self.process_specification(specification_uri)

            if 'er.mineraloccurrence' in name:
                logger.log("Incorrect GML ID {0} in name field".format(name), logger.WARNING)
                if names is not None and len(names) > 0:
                    if self.state == 'vic':
                        name = None
                        logger.log(
                            "Victoria has project names for occurrences, setting name to null to protect original",
                            logger.WARNING)
                    else:
                        name = " - ".join(names)
                        logger.log("Creating name from complex feature: {0}".format(name))
                else:
                    name = None

                if name is None:
                    logger.log("No name found, do not overwrite value in database", logger.WARNING)

            logger.log("State id: {0}, name: {1}".format(otherid, name))

    def check_representative_commodity(self, occurrence):
        """
        TODO: Remove this later
        :param occurrence:
        :return:
        """
        commodity_path = 'erl:representativeCommodity_uri'
        commodity_node = occurrence.find(commodity_path, self.ns)
        if commodity_node is None:
            logger.log(
                "No representative commodity found for {0}".format(self.get_id(occurrence.attrib), logger.WARNING))
            return
        commodity_uri = commodity_node.text
        if commodity_uri not in self.commodity_terms:
            logger.log("Commodity {0} not found in lookup for occurrence {1}".format(commodity_uri,
                                                                                     self.get_id(occurrence.attrib),
                                                                                     logger.WARNING))

    def get_id(self, attrib):
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
        commodity_nodes = root.findall('.//er:MineralOccurrence/er:commodityDescription/er:Commodity', self.ns)
        commodities = self.process_commodities(commodity_nodes)
        return [names, commodities]

    def process_names(self, names_nodes):
        return [name.text for name in names_nodes if (
                    'codeSpace' in name.attrib and name.attrib['codeSpace'] not in ['http://www.ietf.org/rfc/rfc2616',
                                                                                    'http://www.ietf.org/rfc/rfc2141'])]

    def process_commodities(self, commodity_nodes):
        commods = []

        for node in commodity_nodes:
            commod = node.find('er:commodity', self.ns)
            commodname = node.find('er:commodityName', self.ns)

            commodity = None

            if commod is not None:
                commodity = self.get_commodity(commod)
            elif commodname is not None:
                commodity = self.get_commodity(commodname)
            if commodity is None:
                logger.log("No associated commodity for this occurrence", logger.WARNING)

            order = node.find('er:commodityRank', self.ns)
            importance = node.find('er:commodityImportance', self.ns)

            if order is not None and order.text is not None:
                order = int(order.text)
            if importance is not None:
                importance = importance.text

            if order is None and importance is None:
                logger.log("Commodity has no rank or order for this occurrence", logger.WARNING)

            commods.append((commodity, order, importance))
        return commods

    def get_commodity(self, commodity_node):
        commodity = None
        if '{http://www.w3.org/1999/xlink}href' in commodity_node:
            commodity = commodity['{http://www.w3.org/1999/xlink}href']
            if commodity not in self.commodity_terms:
                logger.log("Commodity URI {0} not found in vocabs".format(commodity), logger.WARNING)
        if commodity_node.text is not None and 'urn:cgi:classifier:GA:commodity:' in commodity_node.text:
            commodity = commodity_node.text.replace('urn:cgi:classifier:GA:commodity:','')
            if commodity not in [commod['COMMODID'] for commod in self.commodity_lookup]:
                logger.log("Commodity code {0} not found in lookup for occurrence".format(commodity), logger.WARNING)
        return commodity

    def get_feature(self, uri):
        response = requests.get(uri)
        if response.status_code == 200:
            return response
        else:
            logger.log("Specification uri {0} did not work".format(uri), logger.WARNING)

        feature_id = 'er.' + '.'.join(uri.split('/')[-2:])
        if self.state == 'sa':
            logger.log("Appending \'deposit\' to gml_id for South Australian service")
            feature_id = feature_id + 'deposit'
        parameters = {'service': 'WFS',
                      'version': '1.1.0',
                      'request': 'GetFeature',
                      'typeName': 'er:MineralOccurrence',
                      'featureId': feature_id
                      }
        response = requests.get(self.endpoint, params=parameters)
        logger.log("Calling {0} to get feature specification".format(response.url))
        return response
