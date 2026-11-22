import ast,html,json,math,os,pathlib,re,runpy,sys,types
root=pathlib.Path.cwd();sys.path.insert(0,str(root/'tests'))
from test_bento_open_issues import functions,OpenBentoIssueTests
f=OpenBentoIssueTests();env=f.toolbar_env();env['_capture_toolbar_links'](["<a title=\"AI Assistant\" onclick=\"return pycmd('ankiterminator')\">AI</a>"],None)
external=env['render_reviewer_toolbar_entries']()
aqt=types.ModuleType('aqt');aqt.mw=types.SimpleNamespace(pm=types.SimpleNamespace(profile={'onigiri_language':'en'}));sys.modules['aqt']=aqt
loc=runpy.run_path(str(root/'core/translations.py'));locales={}
for code in loc['LANGUAGES'].values():
 aqt.mw.pm.profile['onigiri_language']=code
 literals=loc['literal_strings']()
 used=set(re.findall(r'onigiriText\("([^"]+)"\)',(root/'things_theme/web/sidebar.js').read_text())) | {'new','due','total','today','Due Today','New Cards','In Learning'}
 literals={key:value for key,value in literals.items() if key in used}
 locales[code]={'literals':literals,'labels':{'due':literals['Due Today'],'new':literals['New Cards'],'learn':literals['In Learning']}}
fontenv={}
for node in ast.parse((root/'ui_kit/fonts.py').read_text()).body:
 if isinstance(node,ast.Assign) and isinstance(node.targets[0],ast.Name) and node.targets[0].id in ['POPPINS_STACK','POPPINS_WEIGHTS','_POPPINS_SUBDIR','FONTS']:
  exec(compile(ast.Module(body=[node],type_ignores=[]),'fonts.py','exec'),fontenv)
functions('ui_kit/fonts.py',{'poppins_font_face_css'},fontenv)
fontmodule=types.ModuleType('fixture.ui_kit.fonts');fontmodule.__dict__.update(fontenv);fontmodule.get_all_fonts=lambda _:fontenv['FONTS'];sys.modules[fontmodule.__name__]=fontmodule
module=types.ModuleType('fixture.api.sidebar');module.render_reviewer_toolbar_entries=lambda:external;sys.modules[module.__name__]=module
conf={'hideNativeHeaderAndBottomBar':True}
data={'done':10,'left':20,'total':30,'pct':33,'new':10,'learn':5,'review':5}
env=dict(__package__='fixture.rendering',__file__=str(root/'rendering/patcher.py'),os=os,html=html,math=math,json=json,re=re,
 config=types.SimpleNamespace(get_config_readonly=lambda:conf,get_collection_config=lambda k,d:{'onigiri_font_main':'space_mono','onigiri_font_size_main':18}.get(k,d)),
 mw=types.SimpleNamespace(col=types.SimpleNamespace(conf={})),tr=lambda k,d=None:d or k,tr_at=lambda k:k,
 _study_tool_header_buttons=lambda _:('',''),reset_reviewer_progress_session=lambda:None,
 _reviewer_progress_counts=lambda:data,_progress_settings_cache={'key':None,'settings':None})
for node in ast.parse((root/'rendering/patcher.py').read_text()).body:
 if isinstance(node,ast.Assign) and isinstance(node.targets[0],ast.Name) and node.targets[0].id in ['_PROGRESS_STYLES','_PROGRESS_LABELS']:
  exec(compile(ast.Module(body=[node],type_ignores=[]),'patcher.py','exec'),env)
functions('rendering/patcher.py',{'generate_box_effect_button_vars_css','_box_effect_values','_onigiri_int_style_value','generate_reviewer_top_bar_html_and_css','generate_scoped_main_font_css','_reviewer_progress_settings','_reviewer_progress_css','_reviewer_progress_html','_reviewer_progress_classes','_reviewer_progress_inner_html','_reviewer_progress_label_text','_reviewer_progress_tooltip'},env)
markup,css=env['generate_reviewer_top_bar_html_and_css'](False)
css=env['generate_scoped_main_font_css']('1011095603','#onigiri-reviewer-header')+env['generate_box_effect_button_vars_css'](conf,'#onigiri-reviewer-header',':host(.night-mode) #onigiri-reviewer-header')+css
faces=re.findall(r'@font-face\s*\{[^{}]*\}',css)
css=re.sub(r'@font-face\s*\{[^{}]*\}','',css).replace('.night_mode #onigiri-reviewer-header',':host(.night-mode) #onigiri-reviewer-header')
print(json.dumps({'locales':locales,'header':markup,'shadowCss':css,'fontFaces':'\n'.join(faces),'fontFamily':fontenv['FONTS']['space_mono']['family']}))
