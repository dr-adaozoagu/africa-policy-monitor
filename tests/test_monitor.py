import importlib.util
from pathlib import Path
import unittest
spec=importlib.util.spec_from_file_location('monitor',Path(__file__).resolve().parents[1]/'scripts/monitor.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class MonitorTests(unittest.TestCase):
 def test_same_domain_keyword_normalisation_and_dedup(self):
  doc='<a href="/health?utm_source=x">New digital health consultation for Africa</a><a href="/health">New digital health consultation for Africa</a><a href="https://evil.test/">Digital health consultation outside the official domain</a><a href="/unrelated">Economic integration discussion session</a>'
  self.assertEqual(m.extract(doc,'https://au.int/',['digital health']),{'https://au.int/health':'New digital health consultation for Africa'})
 def test_first_run_not_new_second_run_new_then_retitled(self):
  state={'sources':{},'items':{}};source={'name':'AU','url':'https://au.int/'}
  base,changes=m.update_source(state,source,{'https://au.int/a':'Digital health baseline'},'t1')
  self.assertTrue(base);self.assertEqual(changes,[])
  _,changes=m.update_source(state,source,{'https://au.int/a':'Digital health baseline','https://au.int/b':'Digital health added'},'t2')
  self.assertEqual(len(changes),1);self.assertEqual(changes[0]['kind'],'newly discovered candidate')
  _,changes=m.update_source(state,source,{'https://au.int/a':'Digital health retitled'},'t3')
  self.assertEqual(changes[0]['kind'],'retitled candidate');self.assertEqual(len(state['items']),2)
 def test_repeated_observation_is_not_new(self):
  state={'sources':{},'items':{}};s={'url':'https://au.int/','name':'AU'};d={'https://au.int/a':'same'}
  m.update_source(state,s,d,'t1');_,changes=m.update_source(state,s,d,'t2');self.assertEqual(changes,[])
 def test_unrelated_redirect_blocked(self):
  req=m.Request('https://au.int/')
  with self.assertRaises(ValueError):
   m.InstitutionalRedirects().redirect_request(req,None,302,'',{},'https://unrelated.test/')
if __name__=='__main__':unittest.main()
