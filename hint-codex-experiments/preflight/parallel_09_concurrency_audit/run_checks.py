"""Record real import paths, then run frozen and candidate integration regressions offline."""
import importlib.util,json,os,re,sys,time,unittest
from pathlib import Path
os.environ['LITELLM_LOCAL_MODEL_COST_MAP']='True'
os.environ['TELEMETRY']='False'
ROOT=Path('/srv/lab-disks/disk2/users/xymo/hint-codex-experiments')
OUT=ROOT/'preflight/parallel_09_concurrency_audit'
mode=sys.argv[1]
if mode=='imports':
    suite=unittest.defaultTestLoader.discover(str(ROOT/'tests_parallel_09'),pattern='test_*.py')
    modules={name:str(Path(module.__file__).resolve()) for name,module in list(sys.modules.items())
             if getattr(module,'__file__',None) and Path(module.__file__).is_file()
             and str(ROOT) in str(Path(module.__file__).resolve()) and name not in ('__main__','__mp_main__')}
    unexpected={name:path for name,path in modules.items() if not (
        path.startswith(str(ROOT/'source_parallel_09')+'/') or path.startswith(str(ROOT/'tests_parallel_09')+'/'))}
    import run_codex_experiments as paired,test_eval_deep_swe
    modules['test_eval_deep_swe.evaluator']=str(Path(test_eval_deep_swe.evaluator.__file__).resolve())
    result={'passed':suite.countTestCases()==106 and not unexpected and paired.ROOT==ROOT,
            'test_count':suite.countTestCases(),'project_modules':modules,'unexpected_project_imports':unexpected,
            'runtime_root':str(paired.ROOT),'tests_executed':False,'real_model_calls':0,
            'note':'Same original unittest discovery; actual module __file__ paths inspected, not inferred from import statements.'}
    (OUT/'import_paths.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'passed':result['passed'],'test_count':result['test_count'],'modules':len(modules)}))
    raise SystemExit(0 if result['passed'] else 1)
source=OUT/'candidate/codex_cli_bridge.py'
spec=importlib.util.spec_from_file_location('codex_cli_bridge',source)
module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
sys.path.insert(0,str(OUT))
suite=unittest.defaultTestLoader.discover(str(ROOT/'tests_parallel_09'),pattern='test_*.py')
import test_concurrency,test_response_delivery,test_retry_notifications
suite.addTests(unittest.defaultTestLoader.loadTestsFromModule(test_concurrency))
suite.addTests(unittest.defaultTestLoader.loadTestsFromModule(test_response_delivery))
suite.addTests(unittest.defaultTestLoader.loadTestsFromModule(test_retry_notifications))
started=time.monotonic()
with (OUT/'candidate_all_tests.log').open('w') as stream:
    result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
record={'passed':result.wasSuccessful(),'tests':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),
        'elapsed_seconds':time.monotonic()-started,'real_model_calls':0,'actual_bridge_module':module.__file__,
        'original_tests':106,'six_lane_concurrent_tests':6,'response_delivery_regressions':11,'retry_notification_regressions':5,
        'formal_experiment_started':False,'frozen_production_modified':False}
(OUT/'candidate_all_tests.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record,indent=2))
raise SystemExit(0 if result.wasSuccessful() else 1)
