import os, threading, requests, asyncio
from flask import Flask, jsonify, send_from_directory
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, ConversationHandler, CallbackQueryHandler, ContextTypes, filters
app=Flask(__name__)
SUPABASE_URL=os.environ.get('SUPABASE_URL','').rstrip('/')
SUPABASE_SECRET_KEY=os.environ.get('SUPABASE_SECRET_KEY','')
BOT_TOKEN=os.environ.get('BOT_TOKEN','')
ADMIN_USER_ID=os.environ.get('ADMIN_USER_ID','')
def hdr(): return {'apikey':SUPABASE_SECRET_KEY,'Authorization':f'Bearer {SUPABASE_SECRET_KEY}','Content-Type':'application/json','Prefer':'return=representation'}
def admin(u): return str(u.effective_user.id)==str(ADMIN_USER_ID)
def rows():
 r=requests.get(f'{SUPABASE_URL}/rest/v1/schemes',headers=hdr(),params={'select':'*','order':'id.desc'},timeout=20); r.raise_for_status(); return r.json()
@app.get('/health')
def health(): return {'ok':True}
@app.get('/api/schemes')
def api():
 try:return jsonify(rows())
 except Exception as e:return jsonify({'error':str(e)}),500
@app.get('/')
def home(): return send_from_directory('.', 'index.html')
NAME,CAT,STATUS,COLOR,IMAGE,DESC,FACTS,EXAM=range(8)
async def start(u,c): await u.message.reply_text('📚 Government Schemes Bot\n\n/add — add scheme (admin)\n/schemes — manage schemes\n/help — help')
async def helpc(u,c): await u.message.reply_text('/add — Add a new scheme\n/schemes — View schemes\n/cancel — Cancel')
async def add(u,c):
 if not admin(u): await u.message.reply_text('⛔ Admin only.'); return ConversationHandler.END
 c.user_data.clear(); await u.message.reply_text('1/8 — Scheme name?'); return NAME
async def name(u,c): c.user_data['name']=u.message.text.strip(); await u.message.reply_text('2/8 — Category?'); return CAT
async def cat(u,c): c.user_data['category']=u.message.text.strip(); await u.message.reply_text('3/8 — Status/badge? (e.g. 2026, UPDATED)'); return STATUS
async def status(u,c): c.user_data['status']=u.message.text.strip(); await u.message.reply_text('4/8 — Card colour? hex like #168a45, or default'); return COLOR
async def color(u,c):
 v=u.message.text.strip(); c.user_data['color']='#168a45' if v.lower()=='default' else v; await u.message.reply_text('5/8 — Image URL? or none'); return IMAGE
async def image(u,c): c.user_data['image']='' if u.message.text.strip().lower()=='none' else u.message.text.strip(); await u.message.reply_text('6/8 — Short description?'); return DESC
async def desc(u,c): c.user_data['description']=u.message.text.strip(); await u.message.reply_text('7/8 — Exam facts, one per line. Example:\nAnnounced in Budget 2026-27.\nTarget: 100 districts.'); return FACTS
async def facts(u,c):
 c.user_data['facts']=[[f'Fact {i+1}',x.strip()] for i,x in enumerate(u.message.text.splitlines()) if x.strip()]; await u.message.reply_text('8/8 — Important exam points, one per line.'); return EXAM
async def exam(u,c):
 c.user_data['exam_facts']=[x.strip() for x in u.message.text.splitlines() if x.strip()]
 d=c.user_data; kb=[[InlineKeyboardButton('✅ Publish',callback_data='publish'),InlineKeyboardButton('❌ Cancel',callback_data='cancel')]]
 await u.message.reply_text(f"📝 PREVIEW\n\n<b>{d['name']}</b>\nCategory: {d['category']}\nStatus: {d['status']}\n\n{d['description']}",parse_mode='HTML',reply_markup=InlineKeyboardMarkup(kb)); return ConversationHandler.END
async def addcb(u,c):
 q=u.callback_query; await q.answer()
 if not admin(u): await q.edit_message_text('⛔ Admin only.'); return
 if q.data=='cancel': c.user_data.clear(); await q.edit_message_text('Cancelled.'); return
 d=c.user_data; payload={k:d[k] for k in ['name','category','status','color','image','description','facts','exam_facts']}
 try:
  r=requests.post(f'{SUPABASE_URL}/rest/v1/schemes',headers=hdr(),json=payload,timeout=20); r.raise_for_status(); c.user_data.clear(); await q.edit_message_text('✅ Published. Stack Card will update automatically.')
 except Exception as e: await q.edit_message_text(f'❌ Publish failed: {e}')
async def schemes(u,c):
 if not admin(u): await u.message.reply_text('⛔ Admin only.'); return
 try:
  data=rows(); kb=[[InlineKeyboardButton(f"{x['id']} • {x['name'][:35]}",callback_data=f"view:{x['id']}")] for x in data[:30]]
  await u.message.reply_text('📚 Schemes:',reply_markup=InlineKeyboardMarkup(kb))
 except Exception as e: await u.message.reply_text(f'❌ Error: {e}')
async def view(u,c):
 q=u.callback_query; await q.answer()
 if not admin(u): await q.edit_message_text('⛔ Admin only.'); return
 sid=q.data.split(':',1)[1]
 r=requests.get(f'{SUPABASE_URL}/rest/v1/schemes',headers=hdr(),params={'id':f'eq.{sid}','select':'*'},timeout=20); r.raise_for_status(); data=r.json()
 if not data: await q.edit_message_text('Not found.'); return
 x=data[0]; kb=[[InlineKeyboardButton('🗑 Delete',callback_data=f'del:{sid}')]]
 await q.edit_message_text(f"📚 <b>{x['name']}</b>\nCategory: {x.get('category','')}\nStatus: {x.get('status','')}\n\n{x.get('description','')}",parse_mode='HTML',reply_markup=InlineKeyboardMarkup(kb))
async def delete(u,c):
 q=u.callback_query; await q.answer()
 if not admin(u): await q.edit_message_text('⛔ Admin only.'); return
 sid=q.data.split(':',1)[1]; r=requests.delete(f'{SUPABASE_URL}/rest/v1/schemes',headers=hdr(),params={'id':f'eq.{sid}'},timeout=20)
 await q.edit_message_text('🗑 Scheme deleted.' if r.ok else f'❌ Delete failed: {r.text}')
def runbot():
    asyncio.set_event_loop(asyncio.new_event_loop())
    a=Application.builder().token(BOT_TOKEN).build()
 conv=ConversationHandler(entry_points=[CommandHandler('add',add)],states={NAME:[MessageHandler(filters.TEXT&~filters.COMMAND,name)],CAT:[MessageHandler(filters.TEXT&~filters.COMMAND,cat)],STATUS:[MessageHandler(filters.TEXT&~filters.COMMAND,status)],COLOR:[MessageHandler(filters.TEXT&~filters.COMMAND,color)],IMAGE:[MessageHandler(filters.TEXT&~filters.COMMAND,image)],DESC:[MessageHandler(filters.TEXT&~filters.COMMAND,desc)],FACTS:[MessageHandler(filters.TEXT&~filters.COMMAND,facts)],EXAM:[MessageHandler(filters.TEXT&~filters.COMMAND,exam)]},fallbacks=[CommandHandler('cancel',lambda u,c:ConversationHandler.END)])
 a.add_handler(CommandHandler('start',start)); a.add_handler(CommandHandler('help',helpc)); a.add_handler(CommandHandler('schemes',schemes)); a.add_handler(conv); a.add_handler(CallbackQueryHandler(addcb,pattern='^(publish|cancel)$')); a.add_handler(CallbackQueryHandler(view,pattern='^view:')); a.add_handler(CallbackQueryHandler(delete,pattern='^del:')); a.run_polling(close_loop=False)
if __name__=='__main__':
 if not all([SUPABASE_URL,SUPABASE_SECRET_KEY,BOT_TOKEN,ADMIN_USER_ID]): raise RuntimeError('Missing required environment variables')
 threading.Thread(target=runbot,daemon=True).start(); app.run(host='0.0.0.0',port=int(os.environ.get('PORT','10000')))
