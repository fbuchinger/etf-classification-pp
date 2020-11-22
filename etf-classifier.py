import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape
import uuid
import heapq
import argparse

from typing import NamedTuple
from itertools import cycle
from collections import defaultdict
from jinja2 import Environment, BaseLoader
import requests
import requests_cache

import csv

requests_cache.install_cache(expire_after=86400) #cache downloaded CSV files for a day
requests_cache.remove_expired_responses()

COLORS = [
  "#EFDECD",
  "#CD9575",
  "#FDD9B5",
  "#78DBE2",
  "#87A96B",
  "#FFA474",
  "#FAE7B5",
  "#9F8170",
  "#FD7C6E",
  "#000000",
  "#ACE5EE",
  "#1F75FE",
  "#A2A2D0",
  "#6699CC",
  "#0D98BA",
  "#7366BD",
  "#DE5D83",
  "#CB4154",
  "#B4674D",
  "#FF7F49",
  "#EA7E5D",
  "#B0B7C6",
  "#FFFF99",
  "#1CD3A2",
  "#FFAACC",
  "#DD4492",
  "#1DACD6",
  "#BC5D58",
  "#DD9475",
  "#9ACEEB",
  "#FFBCD9",
  "#FDDB6D",
  "#2B6CC4",
  "#EFCDB8",
  "#6E5160",
  "#CEFF1D",
  "#71BC78",
  "#6DAE81",
  "#C364C5",
  "#CC6666",
  "#E7C697",
  "#FCD975",
  "#A8E4A0",
  "#95918C",
  "#1CAC78",
  "#1164B4",
  "#F0E891",
  "#FF1DCE",
  "#B2EC5D",
  "#5D76CB",
  "#CA3767",
  "#3BB08F",
  "#FEFE22",
  "#FCB4D5",
  "#FFF44F",
  "#FFBD88",
  "#F664AF",
  "#AAF0D1",
  "#CD4A4C",
  "#EDD19C",
  "#979AAA",
  "#FF8243",
  "#C8385A",
  "#EF98AA",
  "#FDBCB4",
  "#1A4876",
  "#30BA8F",
  "#C54B8C",
  "#1974D2",
  "#FFA343",
  "#BAB86C",
  "#FF7538",
  "#FF2B2B",
  "#F8D568",
  "#E6A8D7",
  "#414A4C",
  "#FF6E4A",
  "#1CA9C9",
  "#FFCFAB",
  "#C5D0E6",
  "#FDDDE6",
  "#158078",
  "#FC74FD",
  "#F78FA7",
  "#8E4585",
  "#7442C8",
  "#9D81BA",
  "#FE4EDA",
  "#FF496C",
  "#D68A59",
  "#714B23",
  "#FF48D0",
  "#E3256B",
  "#EE204D",
  "#FF5349",
  "#C0448F",
  "#1FCECB",
  "#7851A9",
  "#FF9BAA",
  "#FC2847",
  "#76FF7A",
  "#9FE2BF",
  "#A5694F",
  "#8A795D",
  "#45CEA2",
  "#FB7EFD",
  "#CDC5C2",
  "#80DAEB",
  "#ECEABE",
  "#FFCF48",
  "#FD5E53",
  "#FAA76C",
  "#18A7B5",
  "#EBC7DF",
  "#FC89AC",
  "#DBD7D2",
  "#17806D",
  "#DEAA88",
  "#77DDE7",
  "#FFFF66",
  "#926EAE",
  "#324AB2",
  "#F75394",
  "#FFA089",
  "#8F509D",
  "#FFFFFF",
  "#A2ADD0",
  "#FF43A4",
  "#FC6C85",
  "#CDA4DE",
  "#FCE883",
  "#C5E384",
  "#FFAE42"
]

#@dataclass
class ETF:
 
    def __init__ (self, **kwargs):
        self.__dict__.update(kwargs)
        self.holdings = []

    def load_holdings (self):
        if len(self.holdings) == 0:
            self.holdings = ETFHoldingReport()
            self.holdings.load(self.holdinglist_url)
        return self.holdings

isin2name = {}

class ETFHolding(NamedTuple):
    name: str
    isin: str
    country: str
    industry: str
    currency: str
    percentage: float

class ETFHoldingReport:

    def __init__ (self):
        #self.etf_isin = etf_isin
        self.etf_holdings = []
        pass

    def load (self, holdinglist_url):
        self.etf_holdings = []
        response = requests.get(holdinglist_url)
        #response.encoding = "utf-8"
        csvstring = response.text

        holdings = csv.DictReader(csvstring.splitlines()[2:])
        for holding in holdings:
            if holding["Name"] is not None:
                isin2name[holding["ISIN"]] = holding["Name"]
                self.etf_holdings.append(ETFHolding(
                    name = holding["Name"],
                    isin = holding["ISIN"],
                    country = holding["Standort"],
                    currency = holding.get("Marktwährung"),
                    industry = holding.get("Sektor"),
                    percentage = float(holding.get("Gewichtung (%)","0").replace(',', '.'))
                ))
    
    def group_by_key (self,key):
        grouping = defaultdict(float)
        for holding in self.etf_holdings:
            try:
                grouping[holding._asdict()[key]] += holding.percentage
            except:
                pass
        return grouping


class PortfolioPerformanceCategory(NamedTuple):
    name: str
    color: str
    uuid: str    
    

class PortfolioPerformanceFile:

    def __init__ (self, filepath):
        self.filepath = filepath
        self.pp_tree = ET.parse(filepath)
        self.pp = self.pp_tree.getroot()
        self.etfs = []

    def get_etf(self, etf_xpath):
        """return an ETF object if security has ETF holding URL in vendor attribute """
        security =  self.pp.findall(etf_xpath)[0]
        if security is not None:
            sec_attrs = security.findall("attributes/map/entry/string")
            for index, attr in enumerate(sec_attrs):
                if attr.text == "vendor" and sec_attrs[index + 1].text.startswith("https://"):
                    holdinglist_url = sec_attrs[index + 1]

                return ETF(
                    name = security.find('name').text,
                    ISIN = security.find('isin').text,
                    UUID = security.find('uuid').text,
                    ticker = security.find('tickerSymbol').text,
                    issuer = "ishares",
                    holdinglist_url = holdinglist_url.text,
                )
        return None

    def get_etf_xpath_by_uuid (self, uuid):
        for idx, security in enumerate(self.pp.findall(".//securities/security")):
            sec_uuid =  security.find('uuid').text
            if sec_uuid == uuid:
                return f"../../../../../../../../securities/security[{idx + 1}]"

    def add_taxonomy (self, kind):
        etfs = self.get_etfs()
        taxonomy_tpl =  """
            <taxonomy>
                <id>{{ outer_uuid }}</id>
                <name>{{ kind }}</name>
                <root>
                    <id>{{ inner_uuid }}</id>
                    <name>{{ kind }}</name>
                    <color>#89afee</color>
                    <children>
                        {% for category in categories %}
                        <classification>
                            <id>{{ category["uuid"] }}</id>
                            <name>{{ category["name"] }}</name>
                            <color>{{ category["color"] }}</color>
                            <parent reference="../../.."/>
                            <children/>
                            <assignments>
                            {% for assignment in category["assignments"] %}
                                <assignment>
                                    <investmentVehicle class="security" reference="{{ assignment["security_xpath"] }}"/>
                                    <weight>{{ assignment["weight"] }}</weight>
                                    <rank>{{ assignment["rank"] }}</rank>
                                </assignment>
                             {% endfor %}
                            </assignments>
                            <weight>0</weight>
                            <rank>1</rank>
                        </classification>
                        {% endfor %}
                    </children>
                    <assignments/>
                    <weight>10000</weight>
                    <rank>0</rank>
                </root>
            </taxonomy>
            """

        unique_categories = defaultdict(list)

        rank = 1
        for etf in etfs:
            etf_h = etf.load_holdings()
            etf_assignments = etf_h.group_by_key(kind)

            
            for category, weight in etf_assignments.items():
                unique_categories[category].append({
                    "security_xpath":self.get_etf_xpath_by_uuid(etf.UUID),
                    "weight": round(weight*100),
                    "rank": rank
                })
                rank += 1

        categories = []
        color = cycle(COLORS)
        for idx, (category, assignments) in enumerate(unique_categories.items()):
            cat_weight = 0
            for assignment in assignments:
                cat_weight += assignment['weight']


            categories.append({
                "name": escape(isin2name[category]) if kind == "isin" else category,
                "uuid": str(uuid.uuid4()),
                "color": next(color) ,
                "assignments": assignments,
                "weight": cat_weight
            })

        if kind == "isin":
            categories = sorted(categories, key=lambda category: category["weight"], reverse=True) 
            categories = categories[:10]

       
        tax_tpl = Environment(loader=BaseLoader).from_string(taxonomy_tpl)
        taxonomy_xml = tax_tpl.render(
            outer_uuid =  str(uuid.uuid4()),
            inner_uuid =  str(uuid.uuid4()),
            kind = "Top 10 Holdings" if kind == "isin" else kind,
            categories = categories
        )
        self.pp.find('.//taxonomies').append(ET.fromstring(taxonomy_xml))

    def write_xml(self):
        self.pp_tree.write(open('pp_classified.xml', 'w'), encoding="unicode")
        #print (ET.tostring(self.pp, encoding="utf-8"))
        #ET.dump(self.pp, encoding="UTF-8")

    def dump_xml(self):
        print (ET.tostring(self.pp, encoding="utf-8"))

    def get_etfs(self):
        self.etfs = []
        sec_xpaths = []
        for transaction in self.pp.findall('.//portfolio-transaction'): 
            for child in transaction:
                if child.tag == "security":
                    sec_xpaths.append('.//'+ child.attrib["reference"].split('/')[-1])

        for sec_xpath in list(set(sec_xpaths)):
            etf = self.get_etf(sec_xpath)
            if etf is not None:
                self.etfs.append(etf)
        return self.etfs

def print_class (grouped_holding):
    for key, value in sorted(grouped_holding.items(), reverse=True):
        print (key, "\t\t{:.2f}%".format(value))
    print ("-"*30)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
    usage="%(prog)s <portfolio.xml> > autoclassified.portfolio.xml",
    description='\r\n'.join(["reads a portfolio performance xml file and auto-classifies",
                 "the iShares ETFs  in it by currency, country and sector weights",
                 "For each ETF, you need to add a link to its holdings list as described in readme.md"])
    )

    parser.add_argument('input_file', metavar='input_file', type=str,
                   help='path to unencrypted pp.xml file')

    args = parser.parse_args()
    if "input_file" not in args:
        parser.print_help()
    else:
        pp_file = PortfolioPerformanceFile(args.input_file)
        pp_file.add_taxonomy('country')
        pp_file.add_taxonomy('industry')
        pp_file.add_taxonomy('isin')
        pp_file.add_taxonomy('currency')
        pp_file.dump_xml()