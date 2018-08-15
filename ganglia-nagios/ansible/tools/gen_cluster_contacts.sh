#!/bin/python

import yaml
import argparse
import os

DEFAULT_OUTPUT_FILE = "/root/ansible/tools/contact_cluster_maps"

parser = argparse.ArgumentParser()
parser.add_argument("-o", "--outputfile", help="output file containing the mapping between contacts and clusters, \
                                                default is \"%s\"" % DEFAULT_OUTPUT_FILE)

args = parser.parse_args()
if args.outputfile:
  output_file = os.path.abspath(args.outputfile)
else:
  output_file = DEFAULT_OUTPUT_FILE

co_pdu = {}

co_pdu['Kevin Huang'] = ['PDU Cloud', 'PDU CD OMAS', 'PDU CD MIPOS', 'PDU CD Applications', \
                        'PDU MC', 'PDU CC', 'SD']
co_pdu['Xiaoqi Li X'] = ['PDU Cloud', 'PDU CD OMAS', 'PDU CD MIPOS', 'PDU CD Applications', \
                        'PDU MC', 'PDU CC', 'SD']
co_pdu['Eric Zhang K'] = ['PDU Cloud', 'PDU CD OMAS', 'PDU CD MIPOS', 'PDU CD Applications', \
                        'PDU MC', 'PDU CC', 'SD']
co_pdu['Grady Chen'] = ['PDU Cloud', 'PDU CD OMAS', 'PDU CD MIPOS', 'PDU CD Applications', \
                        'PDU MC', 'PDU CC', 'SD']

co_pdu['Ting Yan'] = ['PDU CD ADP CAS', 'PDU CD ADP CAS Support', 'PDU UDM', 'PDU PC']
co_pdu['Claire Ding'] = ['PDU CD ADP CAS', 'PDU CD ADP CAS Support', 'PDU UDM', 'PDU PC']

co_pdu['Seven Dong'] = ['PDU OSS', 'PDU DBSS', 'BNEW BID', 'BNEW PDU TP', 'BNEW SAN', 'BTEB IOT', 'Shared']
co_pdu['Jamie Che'] = ['PDU OSS', 'PDU DBSS', 'BNEW BID', 'BNEW PDU TP', 'BNEW SAN', 'BTEB IOT', 'Shared']
co_pdu['Yongxuan Zhu'] = ['PDU OSS', 'PDU DBSS', 'BNEW BID', 'BNEW PDU TP', 'BNEW SAN', 'BTEB IOT', 'Shared']

pdu_cl = {}

pdu_cl['PDU CD ADP CAS'] = ['adpci01', 'adpci02', 'adpci03', 'adpci04', 'adpci05', 'adpci06', 'adpci07', \
                            'adpci08', 'adpci09', 'adpci10']
pdu_cl['PDU CD ADP CAS Support'] = ['becquerel001']
pdu_cl['PDU CD OMAS'] = ['barrel', 'champ', 'cats', 'cloudsat', 'aquarius', 'cobe']
pdu_cl['PDU CD MIPOS'] = ['hubble', 'hinode', 'topex', 'viking']
pdu_cl['PDU CD Applications'] = ['spitzer', 'surveyor', 'lorentz002', 'lorentz003']
pdu_cl['PDU UDM'] = ['chips', 'trace', 'kepler', 'deimos', 'lorentz001', 'lorentz004']
pdu_cl['PDU PC'] = ['arctas', 'hurricanes', 'artemis', 'ibex']
pdu_cl['PDU OSS'] = ['icon', 'icesat', 'image', 'analog', 'servir', 'rontgen001', 'rontgen002', \
                     'rontgen003', 'rontgen004', 'rontgen005']
pdu_cl['PDU DBSS'] = ['cubesats', 'ladee', 'insight', 'curie001', 'curie002', 'curie003', \
                      'curie004', 'curie005', 'curie006', 'curie007', 'curie008']
pdu_cl['PDU MC'] = ['lucy', 'voyager', 'marconi001']
pdu_cl['PDU CC'] = ['barkla001', 'barkla002']
pdu_cl['SD'] = ['stark001']
pdu_cl['BNEW BID'] = ['integral', 'planck']
pdu_cl['BNEW PDU TP'] = ['zeeman001']
pdu_cl['BNEW SAN'] = ['smith001', 'smith002', 'smith003', 'smith004']
pdu_cl['BTEB IOT'] = ['bohr001']
pdu_cl['Shared'] = ['iris']

c_c = {}

for pdu, cl in pdu_cl.items():
  for c in cl:
    c_c[c] = []
    for co, pl in co_pdu.items():
      if pdu in pl:
        c_c[c].append(co)

with open(output_file, 'w') as output:
  yaml.dump(c_c, output)
  output.close()