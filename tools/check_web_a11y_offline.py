"""Opt-in, offline Chromium UI checks. No install/download/network/provider calls.

Usage: python tools/check_web_a11y_offline.py
Requires an already installed Python Playwright and Chromium. Bypasses HTTP via
set_content because some secured agents block even localhost navigation.
This does NOT validate HTTP, CSP, real API responses or native screen readers.
"""
import json
import os
from pathlib import Path

WEB = Path(__file__).resolve().parents[1] / "src/ai_model_advisor/web"
MOCK = """
window.fetch = async (url, options={}) => {
  const body=options.body?JSON.parse(options.body):{};
  const rec=(label)=>({label,model_id:'synthetic',provider:'openai',effort:'high',
    execution_mode:'direct_api',score:8.2,confidence:0.71,reasons:['Synthetic UX data.']});
  let data, ok=true;
  if(url==='/api/meta') data={version:'test',current_models:2,registry_as_of:'synthetic'};
  else if(url==='/api/decide') {
    if(window.hold) await new Promise(resolve=>window.release=resolve);
    if(body.task.startsWith('ERROR:')) {ok=false; data={error:'Synthetic request error.'};}
    else data={decision_id:'synthetic-only',feedback_options:['primary'],
      decision:{task:body.task,primary:rec('Synthetic model'),cheaper_fallback:null,
        escalation:null,escalation_triggers:['Review manually.'],personal_evidence:[],
        decision_notes:['Heuristic only.'],registry_as_of:'synthetic'}};
  } else if(url==='/api/feedback') {
    window.lastFeedback=body;ok=body.cost_usd!==999;
    data=ok?{saved:true}:{error:'Synthetic save error.'};
  } else {ok=false;data={error:'Unavailable'};}
  return {ok,json:async()=>data};
};
"""

def mount(page):
    html=(WEB/'index.html').read_text(encoding='utf-8')
    html=html.replace('<link rel="stylesheet" href="/app.css">','')
    html=html.replace('<script src="/app.js" defer></script>','')
    page.set_content(html)
    page.add_style_tag(content=(WEB/'app.css').read_text(encoding='utf-8'))
    page.evaluate(MOCK)
    page.add_script_tag(content=(WEB/'app.js').read_text(encoding='utf-8'))

def main():
    from playwright.sync_api import sync_playwright
    report={'method':'rendered DOM; mocked API; not full packaged-app QA','screens':{}}
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path=os.getenv('CHROMIUM_PATH','/usr/bin/chromium'),
                                  headless=True,args=['--no-sandbox'])
        for width in (320,390,768,1440):
            context=browser.new_context(viewport={'width':width,'height':900},
                                        color_scheme='dark',reduced_motion='reduce')
            page=context.new_page();mount(page)
            assert page.locator('#results').is_hidden()
            assert page.locator('#empty').is_visible()
            assert page.evaluate('document.documentElement.scrollWidth === innerWidth')
            page.keyboard.press('Tab')
            assert page.evaluate('document.activeElement.className')=='skip-link'
            page.keyboard.press('Enter')
            assert page.evaluate('document.activeElement.id')=='main-content'
            page.locator('#submit').click()
            assert page.locator('#task').get_attribute('aria-invalid')=='true'
            page.locator('#task').fill('Synthetic audit task.')
            assert page.locator('#form-error').is_hidden()
            page.evaluate('window.hold=true')
            page.locator('#submit').click()
            assert page.locator('#submit').is_disabled()
            assert page.locator('#request-status').is_visible()
            assert page.locator('#results').is_hidden()
            page.evaluate('window.hold=false;window.release()')
            page.get_by_text('Synthetic model').first.wait_for()
            assert page.evaluate('document.activeElement.id')=='primary-name'
            assert page.locator('#empty').is_hidden()
            assert page.locator('#results').is_visible()
            assert page.evaluate('document.documentElement.scrollWidth === innerWidth')
            page.locator('#task').fill('ERROR: synthetic')
            page.locator('#submit').click()
            page.get_by_text('Synthetic request error.').wait_for()
            assert page.locator('#results').is_hidden()
            assert page.evaluate('document.activeElement.id')=='form-error'
            page.locator('#task').fill('Synthetic retry task.')
            page.locator('#submit').click()
            page.get_by_text('Synthetic model').first.wait_for()
            page.locator('#feedback-outcome').select_option('success')
            page.locator('#feedback-cost').fill('999')
            page.locator('#feedback-submit').click()
            page.get_by_text('Synthetic save error.').wait_for()
            assert page.locator('#feedback-submit').is_enabled()
            page.locator('#feedback-cost').fill('0.25')
            page.locator('#feedback-submit').click()
            page.get_by_text('Saved locally.').wait_for()
            assert page.evaluate("!('task' in window.lastFeedback)")
            report['screens'][str(width)]='PASS: reflow, keyboard, empty, loading, result, error, feedback'
            context.close()
        context=browser.new_context(viewport={'width':320,'height':700},
                                    forced_colors='active',reduced_motion='reduce')
        page=context.new_page();mount(page)
        assert page.locator('.segments input:checked+span').evaluate(
            'el=>getComputedStyle(el).outlineStyle')=='solid'
        report['forced_colors']='PASS: visible selected priority outline'
        context.close()
        context=browser.new_context(viewport={'width':320,'height':700},
                                    color_scheme='light',reduced_motion='reduce')
        page=context.new_page();mount(page)
        assert page.locator('h1').is_visible()
        assert page.evaluate('document.documentElement.scrollWidth===innerWidth')
        report['system_light']='PASS: intentional dark design, no reflow'
        context.close()
        browser.close()
    print(json.dumps(report,indent=2))

if __name__=='__main__':
    main()
