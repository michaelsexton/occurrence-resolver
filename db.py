import cx_Oracle
import yaml

with open('database.yml', 'r') as stream:
    credentials = yaml.load(stream)

oraprod = credentials['oraprod']

connection = cx_Oracle.connect(**oraprod)

def get_commodities():
    commodity_sql = 'select commodid, commodname from mgd.commodtypes'

    cursor = connection.cursor()
    cursor.execute(commodity_sql)

    return row_as_dict(cursor)

def row_as_dict(cursor):
    columns = [a[0] for a in cursor.description]

    return [dict(zip(columns, row)) for row in cursor]


