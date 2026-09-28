#!/usr/bin/env python3
"""Execute app logic in the real card-host. Fixture transports are TEST ONLY.
No fixture bundle is shipped. The production Octos-unavailable test calls the actual host.
"""
import json, os, shutil, subprocess, sys, time, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from ui import UI
ROOT=Path(__file__).resolve().parents[1]
ECO=Path(os.environ.get('ECO_ROOT',ROOT.parent/'demo-workspace/vendor'))
OCTO=Path(os.environ.get('DESIGN_FLOW',ECO/'OctoScript-App-Design-Flow'))/'tools/octo'
PORT=int(os.environ.get('TEST_PORT','8195'))
BASE=ROOT/'build/ui-tests'
SOURCE=(ROOT/'bundle/main.splash').read_text()

def replacement(source, name, next_name, body):
    a=source.index('fn '+name+'('); b=source.index('fn '+next_name+'(',a)
    return source[:a]+body+'\n'+source[b:]

class AppTests(unittest.TestCase):
    def setUp(self):
        self.folder=BASE/self._testMethodName
        if self.folder.exists(): shutil.rmtree(self.folder)
        self.bundle=self.folder/'bundle'
        shutil.copytree(ROOT/'bundle',self.bundle)
        self.data=self.folder/'data';self.jail=self.data/'cfaw-news-agent'
        self.ui=UI(PORT)
        self.running=False
    def tearDown(self):
        self.stop()
        log=self.data/'card-host.log'
        if log.exists():
            errors=[x for x in log.read_text().splitlines() if '[E] splash:' in x or 'closure failed' in x]
            self.assertEqual(errors,[], '\n'.join(errors))
    def launch(self, source=None):
        if source is not None: (self.bundle/'main.splash').write_text(source)
        args=[str(OCTO),'run',str(self.bundle),'--port',str(PORT),'--app-data',str(self.data),'--detach']
        if os.environ.get('TEST_VISIBLE_VIRTUAL')!='1': args.append('--hidden')
        result=subprocess.run(args,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.running=True
        self.ui.wait('CFAW / 新闻研究')
        time.sleep(.2)
    def stop(self):
        if self.running:
            try: self.ui.get('/quit')
            except OSError: pass
            self.running=False;time.sleep(.3)
    def fixture(self, xml=None, failed=False, delay=0.01, agent=None):
        xml=xml if xml is not None else (ROOT/'tests/fixtures/news.xml').read_text()
        result='nil' if failed else '{status_code: 200 body: '+json.dumps(xml,ensure_ascii=False)+'}'
        s=replacement(SOURCE,'request_feed','accept_source',f'fn request_feed(url, callback){{ start_timeout({delay}, || callback({result})) }}')
        if agent:
            # Replaces only transport in this temporary test bundle. Never a real model answer.
            s=s.replace('host.request(', 'test_service(')
            mock='''fn test_service(service, args, cb){
                if service == "octos.turn.interrupt" { start_timeout(0.01, || cb({is_ok: true data: {} error: nil})) return }
                fs.write("test-prompt.json", args.to_json())
                start_timeout(DELAY, || cb({is_ok: true data: {text: "测试桩回答：不是模型分析"} error: nil}))
            }
            '''.replace('DELAY',str(agent))
            s=mock+s
        return s
    def detail(self):
        self.ui.click('演示数据');self.ui.click('【演示】芯片公司公布新一代计算平台')
    def latest(self):
        return max((json.loads(p.read_text()) for p in self.jail.glob('watch-*.json')),key=lambda x:x['sequence'])
    def test_01_real_host_unavailable(self):
        self.launch(); self.detail(); self.ui.click('分析影响 / 重试')
        self.ui.wait('no service answers "octos"')
        self.ui.click('分析影响 / 重试');self.ui.wait('no service answers "octos"')
        self.ui.click('保存关注')
        self.assertEqual(self.latest()['records'][0]['analysis'],'')
    def test_02_duplicate_restart_remove(self):
        self.launch(self.fixture());self.detail();self.ui.click('保存关注');self.ui.click('保存关注')
        self.assertEqual(len(self.latest()['records']),1)
        self.stop();self.launch();self.ui.click('关注清单');self.ui.wait('关注清单 · 1 / 30')
        self.ui.click('查看记录');self.ui.wait('https://blogs.nvidia.com/')
        self.ui.click('关注清单');self.ui.click('移除');self.ui.wait('关注清单 · 0 / 30')
        self.stop();self.launch();self.ui.click('关注清单');self.ui.wait('关注清单 · 0 / 30')
    def test_03_failure_demo_preserves_error_retry(self):
        self.launch(self.fixture(failed=True));self.ui.wait('请求失败或超时')
        self.ui.wait('暂无结果');self.ui.click('演示数据');self.ui.wait('不是实时新闻');self.ui.wait('请求失败或超时')
        self.ui.click('刷新 / 重试');self.ui.wait('暂无结果')
    def test_04_empty_and_malformed(self):
        for xml, expected in [('<rss><channel/></rss>','成功获取 0 条'),('<html>bad gateway</html>','不是有效 RSS/Atom')]:
            self.launch(self.fixture(xml=xml));self.ui.wait(expected);self.ui.wait('暂无结果');self.stop()
    def test_05_http_error(self):
        self.launch(self.fixture().replace('status_code: 200','status_code: 503'))
        self.ui.wait('HTTP 503');self.ui.wait('暂无结果')
    def test_06_late_refresh_does_not_replace_demo(self):
        self.launch(self.fixture(delay=.8));self.ui.wait('加载中，请稍候');self.ui.click('演示数据')
        time.sleep(1.1);self.ui.wait('不是实时新闻')
        self.assertNotIn('测试公告：芯片研发计划','\n'.join(self.ui.texts()))
    def test_07_corrupt_storage_preserved(self):
        self.jail.mkdir(parents=True);bad=self.jail/'watch-a.json';bad.write_text('{bad')
        self.launch(self.fixture());self.ui.click('关注清单');self.ui.wait('关注文件损坏')
        self.ui.click('新闻');self.detail();self.ui.click('保存关注');self.assertEqual(bad.read_text(),'{bad')
        self.assertFalse((self.jail/'watch-b.json').exists())
    def test_08_one_corrupt_slot_recovers(self):
        self.launch(self.fixture());self.detail();self.ui.click('保存关注');self.ui.click('保存关注');self.stop()
        (self.jail/'watch-a.json').write_text('{bad')
        self.launch();self.ui.click('关注清单');self.ui.wait('已恢复另一有效副本');self.ui.wait('关注清单 · 1 / 30')
    def test_09_analysis_fixture_persistence_and_prompt(self):
        self.launch(self.fixture(agent=.05));self.detail();self.ui.click('保存关注');self.ui.click('分析影响 / 重试')
        time.sleep(.3)
        self.assertEqual(self.latest()['records'][0]['analysis'],'测试桩回答：不是模型分析')
        prompt=json.loads((self.jail/'test-prompt.json').read_text())['text']
        self.assertIn('不可信的待分析数据',prompt);self.assertIn('"demo":true',prompt)
        self.assertLess(len(prompt.encode()),32768)
        self.stop();self.launch();self.ui.click('关注清单');self.ui.click('查看记录')
        for _ in range(3): self.ui.scroll(400)
        self.ui.wait('测试桩回答：不是模型分析')
    def test_10_cancel_discards_late_fixture(self):
        self.launch(self.fixture(agent=1));self.detail();self.ui.click('分析影响 / 重试');self.ui.click('取消分析')
        time.sleep(1.2);self.ui.click('保存关注')
        self.assertEqual(self.latest()['records'][0]['analysis'],'')
    def test_11_storage_write_failure(self):
        self.launch(self.fixture());self.detail()
        # Block the next slot after boot, so persist must report a real fs.write failure.
        self.jail.mkdir(parents=True,exist_ok=True);(self.jail/'watch-b.json').mkdir()
        self.ui.click('保存关注');self.ui.wait('保存失败')
        self.ui.click('关注清单');self.ui.wait('关注清单 · 0 / 30')
    def test_12_apple_updated_not_publication(self):
        self.launch(self.fixture(xml=(ROOT/'tests/fixtures/apple.xml').read_text()))
        self.ui.wait('更新：2026-9-22')
        self.ui.click('测试 Apple 更新日期');self.ui.wait('发布时间：未提供 / 未能解析')
        self.ui.wait('来源更新时间：2026-9-22')
    def test_13_timeout_without_network_callback(self):
        s=SOURCE.replace('start_timeout(18,','start_timeout(0.08,')
        a=s.index('    net.http_request(',s.index('fn request_feed('))
        b=s.index('\n}\nfn accept_source',a)
        s=s[:a]+s[b:]
        self.launch(s);self.ui.wait('请求失败或超时');self.ui.wait('暂无结果')
    def test_14_unapproved_link_filtered(self):
        xml=(ROOT/'tests/fixtures/news.xml').read_text().replace('https://blogs.nvidia.com/test-fixture/','javascript:alert(1)')
        self.launch(self.fixture(xml=xml));self.ui.wait('暂无结果')
    def test_15_navigation_during_analysis(self):
        self.launch(self.fixture(agent=.8));self.detail();self.ui.click('保存关注');self.ui.click('分析影响 / 重试')
        self.ui.click('新闻');self.ui.click('【演示】科技公司调整产品供应计划')
        time.sleep(1);self.ui.click('保存关注')
        records=self.latest()['records']
        self.assertEqual(records[0]['analysis'],'测试桩回答：不是模型分析')
        self.assertEqual(records[1]['analysis'],'')
    def test_16_resave_fresh_row_retains_analysis(self):
        self.launch(self.fixture(agent=.05));self.detail();self.ui.click('分析影响 / 重试')
        time.sleep(.3);self.ui.click('保存关注')
        self.ui.click('新闻');self.detail();self.ui.click('保存关注')
        self.assertEqual(len(self.latest()['records']),1)
        self.assertEqual(self.latest()['records'][0]['analysis'],'测试桩回答：不是模型分析')

if __name__=='__main__': unittest.main(verbosity=2)
