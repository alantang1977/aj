from __future__ import annotations 
import argparse 
import atexit 
import base64 
import binascii 
import collections 
import contextlib 
import dataclasses 
import datetime 
import gzip 
import hashlib 
import hmac as _hmac 
import http .client 
import http .cookiejar 
from http .server import BaseHTTPRequestHandler ,ThreadingHTTPServer 
import json 
import math 
import os 
import random 
import re 
import secrets 
import shutil 
import signal 
import socket 
import ssl 
import struct 
import sys 
import threading 
import time 
import urllib .error 
import urllib .parse 
import urllib .request 
import uuid 
from collections import deque 
urllib .request .install_opener (urllib .request .build_opener (urllib .request .ProxyHandler ({}))) 
__version__ ='9.5.0'
AUTHOR_COMMUNITY ='https://t.me/garysclub'
AUTHOR_CHANNEL ='https://t.me/garysclubchannel'
AUTHOR_NOTICE =f'''📢 首发地址
社区：Gary's Club ({AUTHOR_COMMUNITY})
频道：Gary's Club Channel ({AUTHOR_CHANNEL})
⚠️ 其他任何分发渠道均非作者本人！'''
AK ='9f5c54c4ed0e50109b800f7e28fec205'
RSA_PUBLIC_KEY_B64 ='MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAkKeLy4ywWLSnBkwRyqYgF3HMIj05V5uuh5HjyEsZOWnu1NHu3jPQv3sr32wwQNYv5qapsNXmNgLUDHtgHZxqPQAYXltjSRc0qhcD286t62wOIHId8zXS3s1Jy4rgU4qjQWzI9rp/1sE0pMsmwTaJa4zuJ5iz8VwF8Av5oJ1k+HxY+/HLnjNlW1hmWLpuDYmkZYuAoTHa1VGeHQh9FEKI8ZcL3GTQphShUoC+Kg3P1hGUVTtCYapmzPS5lkAdwebuzwvTCfGiTErYZCnPBUSeV7BVlgjtLYIi29KvF0a8FHsJMfe/UdHcyW/RihsIYOtDQcRRpFGXyPXbVrzFJse24QIDAQAB'
CLOUD_GET_URL ='https://ytpcloudws.cctv.cn/cloudps/wssapi/device/v2/get'
CLOUD_REGISTER_URL ='https://ytpcloudws.cctv.cn/cloudps/wssapi/device/v2/register'
APP_START_URL ='https://ytpaddr.cctv.cn/gsnw/api/app/start/v1/01'
DRM_CONFIG_URL ='https://ytpaddr.cctv.cn/gsnw/drm/config/obtain/v1'
VERSION_CONFIG_URL ='https://ytpaddr.cctv.cn/gsnw/version/config/obtain/v1'
DICTIONARY_URL ='https://ytpaddr.cctv.cn/gsnw/player/dictionary/obtain/v1'
INDEX_URL ='https://ytpaddr.cctv.cn/gsnw/api/index/v1/01'
REPORT_SINGLE_URL ='https://ytpdata.cctv.cn/das/app/data/message/single'
COLLECT_REPORT_URL ='https://collect.cctv.cn/cctvmobileinf/rest/cctv/receive/new/app'
LIVE_V1_01_URL ='https://ytpaddr.cctv.cn/gsnw/api/live/v1/01'
LIVE_V1_02_URL ='https://ytpaddr.cctv.cn/gsnw/api/live/v1/02'
VDN_GETSTREAM_URL ='https://ytpvdn.cctv.cn/cctvmobileinf/rest/cctv/videoliveUrl/getstream'
DEFAULT_LIVE_USER_ID ='BAEBFF2B-C516-4F34-ABC0-A824A6461CBD'
DEFAULT_DEVICE_NAME ='央视频电视投屏助手'
VDN_APP_NAME ='央视频电视投屏助手'
REPORT_APP_KEY ='1178c84d-4818-44ff-b415-02106e87e144'
COLLECT_SDK_VERSION ='1.0.0'
DEFAULT_PAGE_NAME ='com.cctv.tv.mvp.ui.activity.MainActivity'
DEFAULT_ACCEPT_LANGUAGE ='zh-CN,zh;q=0.8'
RESULT_OK =0 
RESULT_NEEDS_REGISTER =601 
RESULT_GET_MISSING_OR_INVALID =2 
RESULT_REGISTERED_ELSEWHERE =694 
RESULT_REGISTER_RETRY_LATER =695 
_SBOX =(99 ,124 ,119 ,123 ,242 ,107 ,111 ,197 ,48 ,1 ,103 ,43 ,254 ,215 ,171 ,118 ,202 ,130 ,201 ,125 ,250 ,89 ,71 ,240 ,173 ,212 ,162 ,175 ,156 ,164 ,114 ,192 ,183 ,253 ,147 ,38 ,54 ,63 ,247 ,204 ,52 ,165 ,229 ,241 ,113 ,216 ,49 ,21 ,4 ,199 ,35 ,195 ,24 ,150 ,5 ,154 ,7 ,18 ,128 ,226 ,235 ,39 ,178 ,117 ,9 ,131 ,44 ,26 ,27 ,110 ,90 ,160 ,82 ,59 ,214 ,179 ,41 ,227 ,47 ,132 ,83 ,209 ,0 ,237 ,32 ,252 ,177 ,91 ,106 ,203 ,190 ,57 ,74 ,76 ,88 ,207 ,208 ,239 ,170 ,251 ,67 ,77 ,51 ,133 ,69 ,249 ,2 ,127 ,80 ,60 ,159 ,168 ,81 ,163 ,64 ,143 ,146 ,157 ,56 ,245 ,188 ,182 ,218 ,33 ,16 ,255 ,243 ,210 ,205 ,12 ,19 ,236 ,95 ,151 ,68 ,23 ,196 ,167 ,126 ,61 ,100 ,93 ,25 ,115 ,96 ,129 ,79 ,220 ,34 ,42 ,144 ,136 ,70 ,238 ,184 ,20 ,222 ,94 ,11 ,219 ,224 ,50 ,58 ,10 ,73 ,6 ,36 ,92 ,194 ,211 ,172 ,98 ,145 ,149 ,228 ,121 ,231 ,200 ,55 ,109 ,141 ,213 ,78 ,169 ,108 ,86 ,244 ,234 ,101 ,122 ,174 ,8 ,186 ,120 ,37 ,46 ,28 ,166 ,180 ,198 ,232 ,221 ,116 ,31 ,75 ,189 ,139 ,138 ,112 ,62 ,181 ,102 ,72 ,3 ,246 ,14 ,97 ,53 ,87 ,185 ,134 ,193 ,29 ,158 ,225 ,248 ,152 ,17 ,105 ,217 ,142 ,148 ,155 ,30 ,135 ,233 ,206 ,85 ,40 ,223 ,140 ,161 ,137 ,13 ,191 ,230 ,66 ,104 ,65 ,153 ,45 ,15 ,176 ,84 ,187 ,22 )
_RCON =(1 ,2 ,4 ,8 ,16 ,32 ,64 ,128 ,27 ,54 )
def _xtime (a :int )->int :
    return (a <<1 ^283 )&255 if a &128 else a <<1 &255 
def _aes256_key_schedule (key :bytes ):
    assert len (key )==32 
    w =[int .from_bytes (key [i :i +4 ],'big')for i in range (0 ,32 ,4 )]
    for i in range (8 ,60 ):
        temp =w [i -1 ]
        if i %8 ==0 :
            temp =_SBOX [temp >>16 &255 ]<<24 |_SBOX [temp >>8 &255 ]<<16 |_SBOX [temp &255 ]<<8 |_SBOX [temp >>24 &255 ]
            temp ^=_RCON [i //8 -1 ]<<24 
        elif i %8 ==4 :
            temp =_SBOX [temp >>24 &255 ]<<24 |_SBOX [temp >>16 &255 ]<<16 |_SBOX [temp >>8 &255 ]<<8 |_SBOX [temp &255 ]
        w .append (w [i -8 ]^temp )
    return [b''.join ((word .to_bytes (4 ,'big')for word in w [i :i +4 ]))for i in range (0 ,60 ,4 )]
def _add_round_key (state ,rk :bytes ):
    for i in range (16 ):
        state [i ]^=rk [i ]
def _sub_bytes (state ):
    for i in range (16 ):
        state [i ]=_SBOX [state [i ]]
def _shift_rows (s ):
    s [1 ],s [5 ],s [9 ],s [13 ]=(s [5 ],s [9 ],s [13 ],s [1 ])
    s [2 ],s [6 ],s [10 ],s [14 ]=(s [10 ],s [14 ],s [2 ],s [6 ])
    s [3 ],s [7 ],s [11 ],s [15 ]=(s [15 ],s [3 ],s [7 ],s [11 ])
def _mix_columns (s ):
    for c in range (4 ):
        a0 ,a1 ,a2 ,a3 =(s [4 *c ],s [4 *c +1 ],s [4 *c +2 ],s [4 *c +3 ])
        s [4 *c ]=_xtime (a0 )^(_xtime (a1 )^a1 )^a2 ^a3 
        s [4 *c +1 ]=a0 ^_xtime (a1 )^(_xtime (a2 )^a2 )^a3 
        s [4 *c +2 ]=a0 ^a1 ^_xtime (a2 )^(_xtime (a3 )^a3 )
        s [4 *c +3 ]=_xtime (a0 )^a0 ^a1 ^a2 ^_xtime (a3 )
def _aes256_encrypt_block_rk (rk :list ,block :bytes )->bytes :
    s =bytearray (block )
    _add_round_key (s ,rk [0 ])
    for rnd in range (1 ,14 ):
        _sub_bytes (s )
        _shift_rows (s )
        _mix_columns (s )
        _add_round_key (s ,rk [rnd ])
    _sub_bytes (s )
    _shift_rows (s )
    _add_round_key (s ,rk [14 ])
    return bytes (s )
def aes256_encrypt_block (key :bytes ,block :bytes )->bytes :
    return _aes256_encrypt_block_rk (_aes256_key_schedule (key ),block )
def _gf_mult (x :int ,y :int )->int :
    r =299076299051606071403356588563077529600 
    z =0 
    v =y 
    for _ in range (128 ):
        if x &170141183460469231731687303715884105728 :
            z ^=v 
        if v &1 :
            v =v >>1 ^r 
        else :
            v >>=1 
        x =x <<1 &340282366920938463463374607431768211455 
    return z 
def _ghash (h :int ,aad :bytes ,ct :bytes )->int :
    x =0 
    def _blocks (data :bytes ):
        for i in range (0 ,len (data ),16 ):
            blk =data [i :i +16 ]
            if len (blk )<16 :
                blk =blk +b'\x00'*(16 -len (blk ))
            yield int .from_bytes (blk ,'big')
    for b in _blocks (aad ):
        x =_gf_mult (x ^b ,h )
    for b in _blocks (ct ):
        x =_gf_mult (x ^b ,h )
    lens =len (aad )*8 <<64 |len (ct )*8 
    x =_gf_mult (x ^lens ,h )
    return x 
def _inc32 (block :bytes )->bytes :
    ctr =int .from_bytes (block [12 :],'big')
    return block [:12 ]+(ctr +1 &4294967295 ).to_bytes (4 ,'big')
def _gctr_rk (rk :list ,icb :bytes ,data :bytes )->bytes :
    out =bytearray ()
    cb =icb 
    for i in range (0 ,len (data ),16 ):
        ks =_aes256_encrypt_block_rk (rk ,cb )
        chunk =data [i :i +16 ]
        out +=bytes ((a ^b for a ,b in zip (chunk ,ks )))
        cb =_inc32 (cb )
    return bytes (out )
def _gctr (key :bytes ,icb :bytes ,data :bytes )->bytes :
    return _gctr_rk (_aes256_key_schedule (key ),icb ,data )
def aes_gcm_encrypt (key :bytes ,nonce :bytes ,plaintext :bytes ,aad :bytes =b'')->bytes :
    assert len (key )==32 and len (nonce )==12 
    rk =_aes256_key_schedule (key )
    h =int .from_bytes (_aes256_encrypt_block_rk (rk ,b'\x00'*16 ),'big')
    j0 =nonce +b'\x00\x00\x00\x01'
    ct =_gctr_rk (rk ,_inc32 (j0 ),plaintext )
    s =_ghash (h ,aad ,ct ).to_bytes (16 ,'big')
    tag =bytes ((a ^b for a ,b in zip (_aes256_encrypt_block_rk (rk ,j0 ),s )))
    return ct +tag 
def aes_gcm_decrypt (key :bytes ,nonce :bytes ,ct_and_tag :bytes ,aad :bytes =b'')->bytes :
    if len (ct_and_tag )<16 :
        raise ValueError ('AES-GCM payload too short')
    ct ,tag =(ct_and_tag [:-16 ],ct_and_tag [-16 :])
    rk =_aes256_key_schedule (key )
    h =int .from_bytes (_aes256_encrypt_block_rk (rk ,b'\x00'*16 ),'big')
    j0 =nonce +b'\x00\x00\x00\x01'
    s =_ghash (h ,aad ,ct ).to_bytes (16 ,'big')
    expect =bytes ((a ^b for a ,b in zip (_aes256_encrypt_block_rk (rk ,j0 ),s )))
    if not _hmac .compare_digest (tag ,expect ):
        raise ValueError ('AES-GCM decrypt failed')
    return _gctr_rk (rk ,_inc32 (j0 ),ct )
def _mgf1_sha256 (seed :bytes ,length :int )->bytes :
    out =bytearray ()
    counter =0 
    while len (out )<length :
        out +=hashlib .sha256 (seed +counter .to_bytes (4 ,'big')).digest ()
        counter +=1 
    return bytes (out [:length ])
def _oaep_encode_sha256 (message :bytes ,k :int ,seed :bytes )->bytes :
    hlen =32 
    if len (message )>k -2 *hlen -2 :
        raise ValueError ('OAEP message too long')
    lhash =hashlib .sha256 (b'').digest ()
    ps =b'\x00'*(k -len (message )-2 *hlen -2 )
    db =lhash +ps +b'\x01'+message 
    db_mask =_mgf1_sha256 (seed ,k -hlen -1 )
    masked_db =bytes ((a ^b for a ,b in zip (db ,db_mask )))
    seed_mask =_mgf1_sha256 (masked_db ,hlen )
    masked_seed =bytes ((a ^b for a ,b in zip (seed ,seed_mask )))
    return b'\x00'+masked_seed +masked_db 
def _der_read_tlv (der :bytes ,pos :int ):
    assert der [pos ]==48 ,'expected SEQUENCE'
    pos +=1 
    ln ,pos =_der_read_len (der ,pos )
    end =pos +ln 
    items =[]
    while pos <end :
        tag =der [pos ]
        pos +=1 
        ln2 ,pos =_der_read_len (der ,pos )
        items .append ((tag ,der [pos :pos +ln2 ]))
        pos +=ln2 
    return items 
def _der_read_len (der :bytes ,pos :int ):
    first =der [pos ]
    pos +=1 
    if first &128 ==0 :
        return (first ,pos )
    n =first &127 
    return (int .from_bytes (der [pos :pos +n ],'big'),pos +n )
def _der_read_int (raw :bytes )->int :
    return int .from_bytes (raw ,'big')
def parse_spki_rsa_pubkey (der :bytes ):
    outer =_der_read_tlv (der ,0 )
    bitstring =outer [1 ][1 ]
    assert bitstring [0 ]==0 
    inner =_der_read_tlv (bitstring [1 :],0 )
    n =_der_read_int (inner [0 ][1 ])
    e =_der_read_int (inner [1 ][1 ])
    return (n ,e )
def rsa_oaep_sha256_encrypt (der :bytes ,message :bytes ,seed :bytes )->bytes :
    n ,e =parse_spki_rsa_pubkey (der )
    k =(n .bit_length ()+7 )//8 
    em =_oaep_encode_sha256 (message ,k ,seed )
    m =int .from_bytes (em ,'big')
    c =pow (m ,e ,n )
    return c .to_bytes (k ,'big')
class YsptpError (Exception ):
    pass 
def now_f64 ()->float :
    return time .time ()
def current_time_ms ()->int :
    return int (now_f64 ()*1000.0 )
def rust_round (x :float )->float :
    return math .floor (x +0.5 )
def sha1_upper (value :str )->str :
    return hashlib .sha1 (value .encode ('utf-8')).hexdigest ().upper ()
def sha256_hex (value :str )->str :
    return hashlib .sha256 (value .encode ('utf-8')).hexdigest ()
def md5_hex (value :str )->str :
    return hashlib .md5 (value .encode ('utf-8')).hexdigest ()
global_log_ring =collections .deque (maxlen =120 )
_log_lock =threading .Lock ()
_last_log_times ={}
def log (msg ,min_interval =0.0 ):
    now =time .time ()
    clean_msg =str (msg ).strip ()
    if not clean_msg :
        return 
    with _log_lock :
        interval =min_interval if min_interval >0.0 else 1.5 
        last_t =_last_log_times .get (clean_msg ,0.0 )
        if now -last_t <interval :
            return 
        _last_log_times [clean_msg ]=now 
        if len (_last_log_times )>600 :
            _last_log_times .clear ()
        line ='[%s] %s'%(time .strftime ('%H:%M:%S'),clean_msg )
        global_log_ring .append (line )
    print (line ,flush =True )
def java_string_hashcode (value :str )->int :
    h =0 
    for ch in value :
        h =h *31 +ord (ch )&4294967295 
    return h -4294967296 if h &2147483648 else h 
def java_uuid_from_hashes (msb_hash :int ,lsb_hash :int )->str :
    msb =msb_hash &18446744073709551615 
    lsb =lsb_hash &18446744073709551615 
    return f'{msb <<64 |lsb :032x}'
def native_day0_ms (now_s :int )->int :
    return 86400000 *((now_s +28800 )//86400 )-28800000 
def compute_fingerprint (x_uid :str ,now_ms :int ):
    day0_ms =native_day0_ms (now_ms //1000 )
    first =sha256_hex (f'{AK }{x_uid }{now_ms }{day0_ms }')
    return (sha256_hex (first ),now_ms ,day0_ms )
def random_hex_string (length :int )->str :
    return ''.join ((secrets .choice ('0123456789abcdef')for _ in range (length )))
def random_mac_address ()->str :
    raw =bytearray (secrets .token_bytes (6 ))
    raw [0 ]=(raw [0 ]|2 )&254 
    return ':'.join ((f'{b :02x}'for b in raw ))
def sanitize_profile_id (value :str )->str :
    out =[]
    last_underscore =False 
    for ch in value :
        if ch .isascii ()and ch .isalnum ():
            out .append (ch .lower ())
            last_underscore =False 
        elif not last_underscore :
            out .append ('_')
            last_underscore =True 
    return ''.join (out ).strip ('_')
def resolution_from_screen_param (screen_param :str )->str :
    parts =screen_param .split ('-')
    if len (parts )>=2 and parts [0 ]and parts [1 ]:
        return f'{parts [0 ]}*{parts [1 ]}'
    return '3840*2160'
def channels ():
    return [('cctv1','Live1717729995180256'),('cctv2','Live1718261577870260'),('cctv3','Live1718261955077261'),('cctv4','Live1718276148119264'),('cctv5','Live1719474204987287'),('cctv5p','Live1719473996025286'),('cctv7','Live1718276412224269'),('cctv8','Live1718276458899270'),('cctv9','Live1718276503187272'),('cctv10','Live1718276550002273'),('cctv11','Live1718276603690275'),('cctv12','Live1718276623932276'),('cctv13','Live1718276575708274'),('cctv14','Live1718276498748271'),('cctv15','Live1718276319614267'),('cctv16','Live1718276256572265'),('cctv17','Live1718276138318263'),('cctv4k','Live1767871224782105'),('cctv8k','Live1688400593818102'),('cctv164k','Live1704966749996185'),('cgtn','Live1719392219423280'),('cgtnfr','Live1719392670442283'),('cgtnru','Live1719392779653284'),('cgtnar','Live1719392885692285'),('cgtnes','Live1719392560433282'),('cgtndoc','Live1719392360336281')]
def channel_by_name (name :str ):
    for c ,live_id in channels ():
        if c ==name :
            return live_id 
    return None 
def has_http_400 (lower :str )->bool :
    return 'http 400'in lower or 'status=400'in lower 
def is_session_core_http_400 (lower :str )->bool :
    return has_http_400 (lower )and any ((needle in lower for needle in ('app/start','live/v1/01','live/v1/02','vdn','heartbeat')))
def is_control_plane_http_400 (lower :str )->bool :
    return has_http_400 (lower )and any ((needle in lower for needle in ('app/start','dictionary','app event','page event','cloud_get','cloud get','cloud_register','cloud register','device info','heartbeat','index','drm config','version config','live/v1/01','live/v1/02','vdn','collect report')))
def is_session_invalidating_error (message :str )->bool :
    lower =message .lower ()
    return 'app/start'in lower or 'decrypt'in lower or 'session_key'in lower or ('missing encrypted session key'in lower )or is_session_core_http_400 (lower )or ('live/v1/01 http 400'in lower )or ('live/v1/01 http 401'in lower )or ('live/v1/01 http 403'in lower )or ('live/v1/02 http 400'in lower )or ('live/v1/02 http 401'in lower )or ('live/v1/02 http 403'in lower )or ('vdn http 400'in lower )or ('vdn http 401'in lower )or ('vdn http 403'in lower )or ('内部错误'in lower )or ('no usable url'in lower )or ('missing videos'in lower )
def is_identity_recoverable_error (message :str )->bool :
    lower =message .lower ()
    return is_session_invalidating_error (message )or is_control_plane_http_400 (lower )or 'upstream m3u8 http 400'in lower or ('upstream m3u8 http 401'in lower )or ('upstream m3u8 http 403'in lower )or ('upstream m3u8 http 404'in lower )or ('playlist response missing'in lower )or ('invalid playlist status'in lower )or ('connection reset'in lower )or ('connection refused'in lower )or ('operation timed out'in lower )or ('timed out'in lower )or ('network is unreachable'in lower )or ('nodename nor servname'in lower )or ('failed to lookup address'in lower )
def normalize_channel (raw :str )->str :
    key =raw .strip ().strip ('/').lower ()
    if key .endswith ('.m3u8'):
        key =key [:-len ('.m3u8')]
    if key in ('cctv16-4k','cctv16_4k','cctv16/4k','cctv16(4k)'):
        return 'cctv164k'
    return key 
TRUE_4K_CHANNELS ={'cctv4k','cctv8k','cctv164k'}
@dataclasses .dataclass 
class DeviceProfile :
    android_id :str =''
    mac :str =''
    hardware :str =''
    board :str =''
    brand :str =''
    device :str =''
    manufacturer :str =''
    model :str =''
    product :str =''
    tags :str =''
    build_type :str =''
    user :str =''
    resolution :str =''
    display :str =''
    version_id :str =''
    host :str =''
    fingerprint :str =''
    report_model :str =''
    @classmethod 
    def from_dict (cls ,d :dict )->'DeviceProfile':
        return cls (**{f .name :str (d .get (f .name ,''))for f in dataclasses .fields (cls )})
@dataclasses .dataclass 
class DeviceState :
    schema_version :int =1 
    profile_source :str =''
    profile :DeviceProfile =dataclasses .field (default_factory =DeviceProfile )
    screen_param :str =''
    cast_model :str =''
    x_uid :str =''
    cloud_guid :str =''
    registered_at :float =0.0 
    updated_at :float =0.0 
@dataclasses .dataclass 
class Identity :
    x_uid :str =''
    x_fingerprint :str =''
    fingerprint_timestamp_ms :int =0 
    headers :dict =dataclasses .field (default_factory =dict )
@dataclasses .dataclass 
class ChannelEntry :
    channel :str =''
    live_id :str =''
    final_url :str =''
    playback_headers :dict =dataclasses .field (default_factory =dict )
    android_id :str =''
    x_uid :str =''
    rate :str =''
    rate_name :str =''
    raw_live_host :str =''
    final_host :str =''
    refreshed_at :float =0.0 
    expires_at :float =0.0 
    generation :int =0 
    last_refresh_error :str =''
    last_refresh_failed_at :float =0.0 
    session_generation :int =0 
    def fresh (self ,now :float )->bool :
        return bool (self .final_url )and now <self .expires_at 
    def stale_usable (self ,now :float ,ttl :float )->bool :
        return bool (self .final_url )and ttl >0.0 and (now <self .expires_at +ttl )
    @classmethod 
    def from_dict (cls ,d :dict )->'ChannelEntry':
        kwargs ={}
        for f in dataclasses .fields (cls ):
            v =d .get (f .name ,f .default if f .default is not dataclasses .MISSING else None )
            if f .name =='playback_headers':
                v =dict (v )if isinstance (v ,dict )else {}
            kwargs [f .name ]=v 
        return cls (**kwargs )
@dataclasses .dataclass 
class PlaylistCacheEntry :
    body :str =''
    content_type :str =''
    cached_at :float =0.0 
    expires_at :float =0.0 
    final_url :str =''
    android_id :str =''
    proxy_origin :str =''
    proxy_prefix :str =''
@dataclasses .dataclass 
class PlaylistCacheProbe :
    state :str =''
    age_ms :int |None =None 
@dataclasses .dataclass 
class AppStartResult :
    session_key :str =''
@dataclasses .dataclass 
class Live01Result :
    live_url :str =''
    rate :str =''
    rate_name :str =''
@dataclasses .dataclass 
class VdnGetStreamResult :
    final_url :str =''
    app_sign :str =''
    app_random_str :str =''
def inspect_playlist_cache (cached ,entry :ChannelEntry ,proxy_origin :str ,proxy_prefix ,now :float )->PlaylistCacheProbe :
    if cached is None :
        return PlaylistCacheProbe (state ='miss:not_found',age_ms =None )
    age_ms =int (rust_round (max (0.0 ,now -cached .cached_at )*1000.0 ))
    fresh =now <cached .expires_at 
    same_final_url =cached .final_url ==entry .final_url 
    same_android_id =cached .android_id ==entry .android_id 
    same_origin =cached .proxy_origin ==proxy_origin 
    same_prefix =cached .proxy_prefix ==(proxy_prefix or '')
    if fresh and same_final_url and same_android_id and same_origin and same_prefix :
        return PlaylistCacheProbe (state ='hit',age_ms =age_ms )
    reasons =[]
    if not fresh :
        reasons .append ('expired')
    if not same_final_url :
        reasons .append ('final_url_changed')
    if not same_android_id :
        reasons .append ('android_id_changed')
    if not same_origin :
        reasons .append ('origin_changed')
    if not same_prefix :
        reasons .append ('prefix_changed')
    if not reasons :
        reasons .append ('unknown')
    return PlaylistCacheProbe (state ='miss:'+'+'.join (reasons ),age_ms =age_ms )
DEVICE_PROFILE_POOL =[{'source':'sony_8k_pool.XR-85Z9K','brand':'Sony','manufacturer':'Sony','model':'XR-85Z9K','report_model':'XR85Z9K','hardware':'mt5895','board':'mt5895','version_id':'SONYTV.2022.XR_85Z9K','screen_param':'7680-4320-280','cast_model':'XR-85Z9K'},{'source':'sony_8k_pool.XR-75Z9K','brand':'Sony','manufacturer':'Sony','model':'XR-75Z9K','report_model':'XR75Z9K','hardware':'mt5895','board':'mt5895','version_id':'SONYTV.2022.XR_75Z9K','screen_param':'7680-4320-260','cast_model':'XR-75Z9K'},{'source':'sony_8k_pool.XR-85Z9J','brand':'Sony','manufacturer':'Sony','model':'XR-85Z9J','report_model':'XR85Z9J','hardware':'mt5895','board':'mt5895','version_id':'SONYTV.2021.XR_85Z9J','screen_param':'7680-4320-280','cast_model':'XR-85Z9J'},{'source':'sony_8k_pool.XR-75Z9J','brand':'Sony','manufacturer':'Sony','model':'XR-75Z9J','report_model':'XR75Z9J','hardware':'mt5895','board':'mt5895','version_id':'SONYTV.2021.XR_75Z9J','screen_param':'7680-4320-260','cast_model':'XR-75Z9J'},{'source':'sony_8k_pool.KD-98ZG9','brand':'Sony','manufacturer':'Sony','model':'KD-98ZG9','report_model':'KD98ZG9','hardware':'mt5893','board':'mt5893','version_id':'SONYTV.2019.KD_98ZG9','screen_param':'7680-4320-320','cast_model':'KD-98ZG9'},{'source':'sony_8k_pool.KD-85ZG9','brand':'Sony','manufacturer':'Sony','model':'KD-85ZG9','report_model':'KD85ZG9','hardware':'mt5893','board':'mt5893','version_id':'SONYTV.2019.KD_85ZG9','screen_param':'7680-4320-280','cast_model':'KD-85ZG9'},{'source':'sony_8k_pool.KD-85ZH8','brand':'Sony','manufacturer':'Sony','model':'KD-85ZH8','report_model':'KD85ZH8','hardware':'mt5893','board':'mt5893','version_id':'SONYTV.2020.KD_85ZH8','screen_param':'7680-4320-280','cast_model':'KD-85ZH8'},{'source':'sony_8k_pool.KD-75ZH8','brand':'Sony','manufacturer':'Sony','model':'KD-75ZH8','report_model':'KD75ZH8','hardware':'mt5893','board':'mt5893','version_id':'SONYTV.2020.KD_75ZH8','screen_param':'7680-4320-260','cast_model':'KD-75ZH8'},{'source':'samsung_8k_pool.QA85QN900A','brand':'Samsung','manufacturer':'Samsung','model':'QA85QN900A','report_model':'QA85QN900A','hardware':'s5e9925','board':'neo8k','version_id':'SAMSUNGTV.2021.QN900A','screen_param':'7680-4320-280','cast_model':'QA85QN900A'},{'source':'samsung_8k_pool.QA75QN900A','brand':'Samsung','manufacturer':'Samsung','model':'QA75QN900A','report_model':'QA75QN900A','hardware':'s5e9925','board':'neo8k','version_id':'SAMSUNGTV.2021.QN900A','screen_param':'7680-4320-260','cast_model':'QA75QN900A'},{'source':'samsung_8k_pool.QA85QN900B','brand':'Samsung','manufacturer':'Samsung','model':'QA85QN900B','report_model':'QA85QN900B','hardware':'s5e9925','board':'neo8k','version_id':'SAMSUNGTV.2022.QN900B','screen_param':'7680-4320-280','cast_model':'QA85QN900B'},{'source':'samsung_8k_pool.QA75QN900B','brand':'Samsung','manufacturer':'Samsung','model':'QA75QN900B','report_model':'QA75QN900B','hardware':'s5e9925','board':'neo8k','version_id':'SAMSUNGTV.2022.QN900B','screen_param':'7680-4320-260','cast_model':'QA75QN900B'},{'source':'samsung_8k_pool.QA85QN900C','brand':'Samsung','manufacturer':'Samsung','model':'QA85QN900C','report_model':'QA85QN900C','hardware':'s5e9935','board':'neo8k','version_id':'SAMSUNGTV.2023.QN900C','screen_param':'7680-4320-280','cast_model':'QA85QN900C'},{'source':'samsung_8k_pool.QA75QN900C','brand':'Samsung','manufacturer':'Samsung','model':'QA75QN900C','report_model':'QA75QN900C','hardware':'s5e9935','board':'neo8k','version_id':'SAMSUNGTV.2023.QN900C','screen_param':'7680-4320-260','cast_model':'QA75QN900C'},{'source':'samsung_8k_pool.QA85QN900D','brand':'Samsung','manufacturer':'Samsung','model':'QA85QN900D','report_model':'QA85QN900D','hardware':'s5e9945','board':'neo8k','version_id':'SAMSUNGTV.2024.QN900D','screen_param':'7680-4320-280','cast_model':'QA85QN900D'},{'source':'samsung_8k_pool.QA98QN990C','brand':'Samsung','manufacturer':'Samsung','model':'QA98QN990C','report_model':'QA98QN990C','hardware':'s5e9935','board':'neo8k','version_id':'SAMSUNGTV.2023.QN990C','screen_param':'7680-4320-320','cast_model':'QA98QN990C'},{'source':'samsung_8k_pool.QA85QN800C','brand':'Samsung','manufacturer':'Samsung','model':'QA85QN800C','report_model':'QA85QN800C','hardware':'s5e9935','board':'neo8k','version_id':'SAMSUNGTV.2023.QN800C','screen_param':'7680-4320-280','cast_model':'QA85QN800C'},{'source':'samsung_8k_pool.QA75QN800D','brand':'Samsung','manufacturer':'Samsung','model':'QA75QN800D','report_model':'QA75QN800D','hardware':'s5e9945','board':'neo8k','version_id':'SAMSUNGTV.2024.QN800D','screen_param':'7680-4320-260','cast_model':'QA75QN800D'},{'source':'lg_8k_pool.OLED88Z1PCA','brand':'LG','manufacturer':'LGE','model':'OLED88Z1PCA','report_model':'OLED88Z1PCA','hardware':'alpha9gen4','board':'lg8k','version_id':'LGTV.2021.OLED88Z1','screen_param':'7680-4320-320','cast_model':'OLED88Z1PCA'},{'source':'lg_8k_pool.OLED77Z1PCA','brand':'LG','manufacturer':'LGE','model':'OLED77Z1PCA','report_model':'OLED77Z1PCA','hardware':'alpha9gen4','board':'lg8k','version_id':'LGTV.2021.OLED77Z1','screen_param':'7680-4320-260','cast_model':'OLED77Z1PCA'},{'source':'lg_8k_pool.OLED88Z2PCA','brand':'LG','manufacturer':'LGE','model':'OLED88Z2PCA','report_model':'OLED88Z2PCA','hardware':'alpha9gen5','board':'lg8k','version_id':'LGTV.2022.OLED88Z2','screen_param':'7680-4320-320','cast_model':'OLED88Z2PCA'},{'source':'lg_8k_pool.OLED77Z2PCA','brand':'LG','manufacturer':'LGE','model':'OLED77Z2PCA','report_model':'OLED77Z2PCA','hardware':'alpha9gen5','board':'lg8k','version_id':'LGTV.2022.OLED77Z2','screen_param':'7680-4320-260','cast_model':'OLED77Z2PCA'},{'source':'lg_8k_pool.OLED88Z3PCA','brand':'LG','manufacturer':'LGE','model':'OLED88Z3PCA','report_model':'OLED88Z3PCA','hardware':'alpha9gen6','board':'lg8k','version_id':'LGTV.2023.OLED88Z3','screen_param':'7680-4320-320','cast_model':'OLED88Z3PCA'},{'source':'lg_8k_pool.OLED77Z3PCA','brand':'LG','manufacturer':'LGE','model':'OLED77Z3PCA','report_model':'OLED77Z3PCA','hardware':'alpha9gen6','board':'lg8k','version_id':'LGTV.2023.OLED77Z3','screen_param':'7680-4320-260','cast_model':'OLED77Z3PCA'},{'source':'lg_8k_pool.OLED88Z4PCA','brand':'LG','manufacturer':'LGE','model':'OLED88Z4PCA','report_model':'OLED88Z4PCA','hardware':'alpha9gen7','board':'lg8k','version_id':'LGTV.2024.OLED88Z4','screen_param':'7680-4320-320','cast_model':'OLED88Z4PCA'},{'source':'lg_8k_pool.86QNED99','brand':'LG','manufacturer':'LGE','model':'86QNED99','report_model':'86QNED99','hardware':'alpha9gen4','board':'lg8k','version_id':'LGTV.2021.86QNED99','screen_param':'7680-4320-300','cast_model':'86QNED99'},{'source':'sony_4k_pool.XR-85X95K','brand':'Sony','manufacturer':'Sony','model':'XR-85X95K','report_model':'XR85X95K','hardware':'mt5895','board':'mt5895','version_id':'SONYTV.2022.XR_85X95K','screen_param':'3840-2160-300','cast_model':'XR-85X95K'},{'source':'sony_4k_pool.XR-75X95K','brand':'Sony','manufacturer':'Sony','model':'XR-75X95K','report_model':'XR75X95K','hardware':'mt5895','board':'mt5895','version_id':'SONYTV.2022.XR_75X95K','screen_param':'3840-2160-280','cast_model':'XR-75X95K'},{'source':'sony_4k_pool.XR-65X90K','brand':'Sony','manufacturer':'Sony','model':'XR-65X90K','report_model':'XR65X90K','hardware':'mt5895','board':'mt5895','version_id':'SONYTV.2022.XR_65X90K','screen_param':'3840-2160-260','cast_model':'XR-65X90K'},{'source':'sony_4k_pool.XR-55X90K','brand':'Sony','manufacturer':'Sony','model':'XR-55X90K','report_model':'XR55X90K','hardware':'mt5895','board':'mt5895','version_id':'SONYTV.2022.XR_55X90K','screen_param':'3840-2160-240','cast_model':'XR-55X90K'},{'source':'sony_4k_pool.XR-65A95K','brand':'Sony','manufacturer':'Sony','model':'XR-65A95K','report_model':'XR65A95K','hardware':'mt5895','board':'mt5895','version_id':'SONYTV.2022.XR_65A95K','screen_param':'3840-2160-260','cast_model':'XR-65A95K'},{'source':'samsung_4k_pool.QA85QN90C','brand':'Samsung','manufacturer':'Samsung','model':'QA85QN90C','report_model':'QA85QN90C','hardware':'s5e9935','board':'neo4k','version_id':'SAMSUNGTV.2023.QN90C','screen_param':'3840-2160-300','cast_model':'QA85QN90C'},{'source':'samsung_4k_pool.QA75QN90C','brand':'Samsung','manufacturer':'Samsung','model':'QA75QN90C','report_model':'QA75QN90C','hardware':'s5e9935','board':'neo4k','version_id':'SAMSUNGTV.2023.QN90C','screen_param':'3840-2160-280','cast_model':'QA75QN90C'},{'source':'samsung_4k_pool.QA65QN90C','brand':'Samsung','manufacturer':'Samsung','model':'QA65QN90C','report_model':'QA65QN90C','hardware':'s5e9935','board':'neo4k','version_id':'SAMSUNGTV.2023.QN90C','screen_param':'3840-2160-260','cast_model':'QA65QN90C'},{'source':'samsung_4k_pool.QA55QN90C','brand':'Samsung','manufacturer':'Samsung','model':'QA55QN90C','report_model':'QA55QN90C','hardware':'s5e9935','board':'neo4k','version_id':'SAMSUNGTV.2023.QN90C','screen_param':'3840-2160-240','cast_model':'QA55QN90C'},{'source':'samsung_4k_pool.QA65S95C','brand':'Samsung','manufacturer':'Samsung','model':'QA65S95C','report_model':'QA65S95C','hardware':'s5e9935','board':'oled4k','version_id':'SAMSUNGTV.2023.S95C','screen_param':'3840-2160-260','cast_model':'QA65S95C'},{'source':'lg_4k_pool.OLED83C3PCA','brand':'LG','manufacturer':'LGE','model':'OLED83C3PCA','report_model':'OLED83C3PCA','hardware':'alpha9gen6','board':'lg4k','version_id':'LGTV.2023.OLED83C3','screen_param':'3840-2160-300','cast_model':'OLED83C3PCA'},{'source':'lg_4k_pool.OLED77C3PCA','brand':'LG','manufacturer':'LGE','model':'OLED77C3PCA','report_model':'OLED77C3PCA','hardware':'alpha9gen6','board':'lg4k','version_id':'LGTV.2023.OLED77C3','screen_param':'3840-2160-280','cast_model':'OLED77C3PCA'},{'source':'lg_4k_pool.OLED65C3PCA','brand':'LG','manufacturer':'LGE','model':'OLED65C3PCA','report_model':'OLED65C3PCA','hardware':'alpha9gen6','board':'lg4k','version_id':'LGTV.2023.OLED65C3','screen_param':'3840-2160-260','cast_model':'OLED65C3PCA'},{'source':'lg_4k_pool.OLED55C3PCA','brand':'LG','manufacturer':'LGE','model':'OLED55C3PCA','report_model':'OLED55C3PCA','hardware':'alpha9gen6','board':'lg4k','version_id':'LGTV.2023.OLED55C3','screen_param':'3840-2160-240','cast_model':'OLED55C3PCA'},{'source':'lg_4k_pool.86QNED90','brand':'LG','manufacturer':'LGE','model':'86QNED90','report_model':'86QNED90','hardware':'alpha7gen5','board':'lg4k','version_id':'LGTV.2022.86QNED90','screen_param':'3840-2160-300','cast_model':'86QNED90'},{'source':'tcl_8k_pool.85X925PRO','brand':'TCL','manufacturer':'TCL','model':'85X925 PRO','report_model':'85X925PRO','hardware':'mt9615','board':'tcl8k','version_id':'TCLTV.2021.X925PRO','screen_param':'7680-4320-280','cast_model':'85X925 PRO'},{'source':'tcl_8k_pool.75X925PRO','brand':'TCL','manufacturer':'TCL','model':'75X925 PRO','report_model':'75X925PRO','hardware':'mt9615','board':'tcl8k','version_id':'TCLTV.2021.X925PRO','screen_param':'7680-4320-260','cast_model':'75X925 PRO'},{'source':'tcl_4k_pool.85C845','brand':'TCL','manufacturer':'TCL','model':'85C845','report_model':'85C845','hardware':'mt9615','board':'tcl4k','version_id':'TCLTV.2023.C845','screen_param':'3840-2160-300','cast_model':'85C845'},{'source':'tcl_4k_pool.75C845','brand':'TCL','manufacturer':'TCL','model':'75C845','report_model':'75C845','hardware':'mt9615','board':'tcl4k','version_id':'TCLTV.2023.C845','screen_param':'3840-2160-280','cast_model':'75C845'},{'source':'tcl_4k_pool.65C845','brand':'TCL','manufacturer':'TCL','model':'65C845','report_model':'65C845','hardware':'mt9615','board':'tcl4k','version_id':'TCLTV.2023.C845','screen_param':'3840-2160-260','cast_model':'65C845'},{'source':'tcl_4k_pool.75C745','brand':'TCL','manufacturer':'TCL','model':'75C745','report_model':'75C745','hardware':'mt9615','board':'tcl4k','version_id':'TCLTV.2023.C745','screen_param':'3840-2160-280','cast_model':'75C745'},{'source':'tcl_4k_pool.65C745','brand':'TCL','manufacturer':'TCL','model':'65C745','report_model':'65C745','hardware':'mt9615','board':'tcl4k','version_id':'TCLTV.2023.C745','screen_param':'3840-2160-260','cast_model':'65C745'},{'source':'changhong_4k_pool.U65G7','brand':'CHANGHONG','manufacturer':'CHANGHONG','model':'U65G7','report_model':'U65G7','hardware':'mt9632','board':'changhong4k','version_id':'CHANGHONGTV.2022.U65G7','screen_param':'3840-2160-260','cast_model':'U65G7'},{'source':'changhong_4k_pool.U55G7','brand':'CHANGHONG','manufacturer':'CHANGHONG','model':'U55G7','report_model':'U55G7','hardware':'mt9632','board':'changhong4k','version_id':'CHANGHONGTV.2022.U55G7','screen_param':'3840-2160-240','cast_model':'U55G7'},{'source':'changhong_4k_pool.L55QCN1','brand':'CHANGHONG','manufacturer':'CHANGHONG','model':'L55QCN1','report_model':'L55QCN1','hardware':'mt9632','board':'changhong4k','version_id':'CHANGHONGTV.2021.L55QCN1','screen_param':'3840-2160-240','cast_model':'L55QCN1'},{'source':'changhong_4k_pool.U43QCN1','brand':'CHANGHONG','manufacturer':'CHANGHONG','model':'U43QCN1','report_model':'U43QCN1','hardware':'mt9632','board':'changhong4k','version_id':'CHANGHONGTV.2021.U43QCN1','screen_param':'3840-2160-220','cast_model':'U43QCN1'},{'source':'changhong_4k_pool.UD65YC5500UA','brand':'CHANGHONG','manufacturer':'CHANGHONG','model':'UD65YC5500UA','report_model':'UD65YC5500UA','hardware':'mt9632','board':'changhong4k','version_id':'CHANGHONGTV.2020.UD65YC5500UA','screen_param':'3840-2160-260','cast_model':'UD65YC5500UA'}]
def random_device_template ()->dict :
    pool_8k =[t for t in DEVICE_PROFILE_POOL if '8k'in t .get ('source','')]
    return secrets .choice (pool_8k if pool_8k else DEVICE_PROFILE_POOL )
def device_profile_from_template (template :dict ,android_id :str ,mac :str )->DeviceProfile :
    brand_id =sanitize_profile_id (template ['brand'])
    model_id =sanitize_profile_id (template ['model'])
    device =f'{brand_id }_{model_id }'
    product =f'{brand_id }_{model_id }'
    return DeviceProfile (android_id =android_id ,mac =mac ,hardware =template ['hardware'],board =template ['board'],brand =template ['brand'],device =device ,manufacturer =template ['manufacturer'],model =template ['model'],product =product ,tags ='release-keys',build_type ='user',user ='build',resolution =resolution_from_screen_param (template ['screen_param']),display =f"{template ['model']}-user 13 {template ['version_id']} 2024 release-keys",version_id =template ['version_id'],host =f'{brand_id }-tv-build',fingerprint =f"{template ['manufacturer']}/{product }/{device }:13/{template ['version_id']}/2024:user/release-keys",report_model =template ['report_model'])
def default_device_state ()->DeviceState :
    template =random_device_template ()
    profile =device_profile_from_template (template ,random_hex_string (16 ),random_mac_address ())
    return DeviceState (schema_version =1 ,profile_source =template ['source'],profile =profile ,screen_param =template ['screen_param'],cast_model =template ['cast_model'],x_uid =compute_x_uid (profile ),cloud_guid ='',registered_at =0.0 ,updated_at =now_f64 ())
def create_and_save_new_device (path :str )->DeviceState :
    new_state =default_device_state ()
    new_state .updated_at =now_f64 ()
    try :
        save_device_state (path ,new_state )
    except OSError :
        pass 
    return new_state 
def binary_dir ()->str :
    return os .path .dirname (os .path .abspath (__file__ ))or '.'
def load_device_state (path :str ):
    try :
        with open (path ,encoding ='utf-8')as f :
            text =f .read ()
    except OSError :
        return (default_device_state (),False )
    try :
        data =json .loads (text )
    except ValueError :
        return (default_device_state (),False )
    try :
        profile =DeviceProfile .from_dict (data .get ('profile',{}))
        state =DeviceState (schema_version =int (data .get ('schema_version',1 )),profile_source =str (data .get ('profile_source','')),profile =profile ,screen_param =str (data .get ('screen_param','')),cast_model =str (data .get ('cast_model','')),x_uid =str (data .get ('x_uid','')),cloud_guid =str (data .get ('cloud_guid','')),registered_at =float (data .get ('registered_at',0.0 )),updated_at =float (data .get ('updated_at',0.0 )))
    except (ValueError ,TypeError ,AttributeError ):
        return (default_device_state (),False )
    if len (state .profile .android_id )!=16 or not state .profile .mac :
        return (default_device_state (),False )
    state .x_uid =compute_x_uid (state .profile )
    if not state .screen_param :
        state .screen_param ='7680-4320-280'
    if not state .cast_model :
        state .cast_model =state .profile .model 
    return (state ,True )
def save_device_state (path :str ,state :DeviceState )->None :
    tmp_path =path +f'.tmp.{os .getpid ()}'
    try :
        parent =os .path .dirname (os .path .abspath (path ))
        if parent :
            os .makedirs (parent ,exist_ok =True )
        with open (tmp_path ,'w',encoding ='utf-8')as f :
            f .write (json .dumps (dataclasses .asdict (state ),indent =2 ,ensure_ascii =False ,sort_keys =True )+'\n')
            f .flush ()
            os .fsync (f .fileno ())
        os .replace (tmp_path ,path )
    except OSError :
        try :
            if os .path .exists (tmp_path ):
                os .remove (tmp_path )
        except OSError :
            pass 
def infer_os_version (profile :DeviceProfile )->str :
    if ':'in profile .fingerprint :
        tail =profile .fingerprint .split (':',1 )[1 ]
        if '/'in tail :
            return tail .split ('/',1 )[0 ]
    return ''
def infer_sdk_int (profile :DeviceProfile )->str :
    major =infer_os_version (profile ).split ('.')[0 ]if infer_os_version (profile )else ''
    return {'13':'33','12':'31','11':'30','10':'29','9':'28','8':'26','7':'24','6':'23'}.get (major ,'')
def compute_x_uid (profile :DeviceProfile )->str :
    build_identity_str ='1698'+profile .hardware +profile .board +profile .brand +profile .device +profile .manufacturer +profile .model +profile .product +profile .tags +profile .build_type +profile .user +profile .resolution +profile .mac 
    uuid_part =java_uuid_from_hashes (java_string_hashcode (build_identity_str ),java_string_hashcode (profile .model ))
    return sha1_upper (f'{profile .android_id }|{uuid_part }')
def build_identity (profile :DeviceProfile ,app_channel :str ,version :str )->Identity :
    x_uid =compute_x_uid (profile )
    x_fingerprint ,ts ,_day0 =compute_fingerprint (x_uid ,current_time_ms ())
    headers ={'Accept':'application/json','Accept-Language':DEFAULT_ACCEPT_LANGUAGE ,'Referer':'api.cctv.cn','User-Agent':'cctv_app_tv','UID':profile .android_id ,'appChannel':app_channel ,'X-Uid':x_uid ,'X-Fingerprint':x_fingerprint ,'X-Version':version ,'Content-Type':'application/json; charset=utf-8','Connection':'Keep-Alive','Accept-Encoding':'gzip','Cache-Control':'no-cache'}
    return Identity (x_uid =x_uid ,x_fingerprint =x_fingerprint ,fingerprint_timestamp_ms =ts ,headers =headers )
def next_request_timestamp_ms ()->int :
    return current_time_ms ()
def fresh_headers (template :dict ,content_type :str ,accept =None ,force_ts =None )->dict :
    headers ={}
    if accept is not None :
        headers ['Accept']=accept 
    req_ts =force_ts if force_ts is not None else next_request_timestamp_ms ()
    headers ['X-Timestamp']=str (req_ts )
    headers ['X-Nonce']=str (uuid .uuid4 ())
    for key in ('Accept-Language', 'Referer', 'User-Agent', 'UID', 'appChannel', 'X-Uid', 'X-Fingerprint', 'X-Version'):
        if key in template:
            headers[key] = template[key]
    if content_type :
        headers ['Content-Type']=content_type 
    for key in ('Connection','Accept-Encoding','Cache-Control'):
        if key in template :
            headers [key ]=template [key ]
    return headers 
def compact_json_bytes (value ,escape_forward_slashes :bool )->bytes :
    text =json .dumps (value ,separators =(',',':'),ensure_ascii =False ,sort_keys =True )
    if escape_forward_slashes :
        text =text .replace ('/','\\/')
    return text .encode ('utf-8')
def normalize_aes_key (value :str )->bytes :
    raw =value .encode ('utf-8')
    return (raw +b'\x00'*32 )[:32 ]
def aes_gcm_decrypt_b64 (value :str ,key :str )->str :
    try :
        raw =base64 .b64decode (value ,validate =True )
    except (binascii .Error ,ValueError )as e :
        raise YsptpError (f'base64 decode failed: {e }')
    if len (raw )<=12 :
        raise YsptpError ('AES-GCM payload too short')
    try :
        plain =aes_gcm_decrypt (normalize_aes_key (key ),raw [:12 ],raw [12 :])
    except ValueError :
        raise YsptpError ('AES-GCM decrypt failed')
    try :
        return plain .decode ('utf-8')
    except UnicodeDecodeError as e :
        raise YsptpError (f'AES-GCM plaintext is not UTF-8: {e }')
def aes_gcm_encrypt_b64 (value :str ,key :str )->str :
    nonce =secrets .token_bytes (12 )
    try :
        encrypted =aes_gcm_encrypt (normalize_aes_key (key ),nonce ,value .encode ('utf-8'))
    except ValueError :
        raise YsptpError ('AES-GCM encrypt failed')
    return base64 .b64encode (nonce +encrypted ).decode ('ascii')
def rsa_encrypt_device_id (device_id :str )->str :
    try :
        der =base64 .b64decode (RSA_PUBLIC_KEY_B64 ,validate =True )
    except (binascii .Error ,ValueError )as e :
        raise YsptpError (f'RSA public key base64 decode failed: {e }')
    n ,e =parse_spki_rsa_pubkey (der )
    k =(n .bit_length ()+7 )//8 
    hlen =32 
    chunk_size =k -2 *hlen -2 
    out =bytearray ()
    data =device_id .encode ('utf-8')
    for i in range (0 ,len (data ),chunk_size ):
        chunk =data [i :i +chunk_size ]
        out +=rsa_oaep_sha256_encrypt (der ,chunk ,secrets .token_bytes (hlen ))
    return base64 .b64encode (bytes (out )).decode ('ascii')
def report_model_from_build (profile :DeviceProfile )->str :
    return profile .model .replace (profile .manufacturer ,'').replace (' ','')
def app_start_field (value ,limit :int )->str :
    return str (value )[:limit ]if limit >=0 else str (value )
def build_report_common_value (profile :DeviceProfile ,x_uid :str ,app_channel :str ,version :str ,sdk_version :str ,data_time_ms :int )->dict :
    model =profile .report_model or report_model_from_build (profile )
    return {'cctv_id':app_start_field (x_uid ,64 ),'device_id':app_start_field (profile .android_id ,64 ),'idfa':'','idfv':'','user_id':'','app_key':app_start_field (REPORT_APP_KEY ,64 ),'imei':'','android_id':app_start_field (profile .android_id ,64 ),'mac':app_start_field (profile .mac ,64 ),'device_builder_type':app_start_field (profile .build_type ,64 ),'device_hardware':app_start_field (profile .hardware ,64 ),'device_board':app_start_field (profile .board ,64 ),'device_brand':app_start_field (profile .brand ,64 ),'device_params':app_start_field (profile .device ,64 ),'device_display':app_start_field (profile .display ,64 ),'device_version_id':app_start_field (profile .version_id ,64 ),'device_host':app_start_field (profile .host ,128 ),'device_product':app_start_field (profile .product ,64 ),'device_tags':app_start_field (profile .tags ,64 ),'device_user':app_start_field (profile .user ,30 ),'device_fingerprint':app_start_field (profile .fingerprint ,128 ),'device_manufacturer':app_start_field (profile .manufacturer ,64 ),'device_model':app_start_field (model ,50 ),'device_resolution':app_start_field (profile .resolution ,20 ),'system_type':'Android','device_type':'TV','app_language':'CHINESE','app_version':app_start_field (version ,30 ),'sdk_version':app_start_field (sdk_version ,30 ),'os_version':app_start_field (infer_os_version (profile ),20 ),'app_channel':app_start_field (app_channel ,50 ),'data_time':app_start_field (data_time_ms ,13 )}
def build_app_start_body (profile :DeviceProfile ,x_uid :str ,app_channel :str ,version :str ,data_time_ms :int )->dict :
    return {'key':'app_start_d1','value':build_report_common_value (profile ,x_uid ,app_channel ,version ,'',data_time_ms )}
def build_collect_headers (profile :DeviceProfile )->dict :
    release =infer_os_version (profile )
    return {'Content-type':'application/x-www-form-urlencoded','Charset':'UTF-8','User-Agent':'Dalvik/2.1.0 (Linux; U; Android '+(release if release else 'Android')+f'; {profile .model } Build/{profile .version_id })','Connection':'Keep-Alive','Accept-Encoding':'gzip'}
def parse_result_code (value )->int |None :
    if isinstance (value ,dict ):
        for key in ('result','code','errCode','errcode','ret'):
            if key in value :
                raw =value [key ]
                if isinstance (raw ,bool ):
                    continue 
                if isinstance (raw ,int ):
                    return raw 
                if isinstance (raw ,str ):
                    try :
                        return int (raw )
                    except ValueError :
                        pass 
        for key in ('data','error','response'):
            if key in value :
                found =parse_result_code (value [key ])
                if found is not None :
                    return found 
    return None 
def extract_guid (value )->str :
    if isinstance (value ,dict ):
        data =value .get ('data')
        if isinstance (data ,dict ):
            guid =data .get ('guid')
            if isinstance (guid ,str ):
                return guid 
    return ''
def root_headers (version :str )->dict :
    return {'X-Uid':'ROOT','X-Fingerprint':'ROOT','X-Nonce':str (uuid .uuid4 ()),'X-Timestamp':str (next_request_timestamp_ms ()),'X-Version':version ,'UID':'ROOT','Referer':'api.cctv.cn','User-Agent':'cctv_app_tv','appChannel':'ROOT','Connection':'Keep-Alive','Accept-Encoding':'gzip'}
def build_vdn_appcommon (version :str )->str :
    return json .dumps ({'adid':'','av':version ,'an':VDN_APP_NAME ,'ap':'cctv_app_tv'},separators =(',',':'),ensure_ascii =False ,sort_keys =True )
def url_host (url :str )->str :
    try :
        return urllib .parse .urlsplit (url ).hostname or ''
    except ValueError :
        return ''
def live_playback_host_needs_signed_headers (host :str )->bool :
    lower =host .lower ()
    return 'liveali'in lower or 'liveten'in lower 
def default_cctv_playback_headers (uid :str )->dict :
    return {'UID':uid ,'APPID':AK ,'Referer':'api.cctv.cn','User-Agent':'cctv_app_tv'}
def cctv_playback_headers_for_entry (entry :ChannelEntry )->dict :
    headers =default_cctv_playback_headers (entry .android_id )
    for key in ('UID','APPID','APPRANDOMSTR','Referer','User-Agent','APPSIGN'):
        value =entry .playback_headers .get (key )
        if value :
            headers [key ]=value 
    return headers 
def entry_missing_signed_playback_headers (entry :ChannelEntry )->bool :
    host =entry .final_host or url_host (entry .final_url )
    if not live_playback_host_needs_signed_headers (host ):
        return False 
    for key in ('APPID','APPSIGN','APPRANDOMSTR'):
        value =entry .playback_headers .get (key ,'')
        if not value .strip ():
            return True 
    return False 
def ts_path_matches_final_url (ts_path :str ,final_url :str )->bool :
    try :
        parsed =urllib .parse .urlsplit (final_url )
    except ValueError :
        return False 
    prefix =parsed .path 
    if prefix .endswith ('.m3u8'):
        prefix =prefix [:-len ('.m3u8')]
    return bool (prefix )and ts_path .startswith (prefix )
def generate_app_random_str ()->str :
    return f'{secrets .randbits (32 ):08x}-0000-{secrets .randbits (32 )&65535 :04x}-0000-00000000{secrets .randbits (32 )&65535 :04x}'
def compute_vdn_code (app_secret :str ,random_str =None ):
    r =random_str if random_str is not None else generate_app_random_str ()
    return (md5_hex (f'{AK }{app_secret }{r }'),r )
def is_ts_url (value :str )->bool :
    try :
        path =urllib .parse .urlsplit (value ).path 
    except ValueError :
        return False 
    return path .lower ().endswith ('.ts')
def _rs_lines (text :str ):
    norm =text .replace ('\r\n','\n')
    lines =norm .split ('\n')
    if norm .endswith ('\n'):
        lines .pop ()
    return [ln [:-1 ]if ln .endswith ('\r')else ln for ln in lines ]
def rewrite_playlist_urls (text :str ,base_url :str )->str :
    try :
        parts =urllib .parse .urlsplit (base_url )
        has_base =bool (parts .scheme and parts .netloc )
    except ValueError :
        has_base =False 
    out =[]
    for line in _rs_lines (text ):
        stripped =line .strip ()
        if not stripped or stripped .startswith ('#'):
            out .append (line )
        elif has_base :
            out .append (urllib .parse .urljoin (base_url ,stripped ))
        else :
            out .append (stripped )
    return ''.join ((ln +'\n'for ln in out ))
def header_value_clean (value :str )->str :
    return value .replace ('\r','').replace ('\n','')
def form_urlencode_value (s :str )->str :
    out =[]
    for byte in s .encode ('utf-8'):
        ch =chr (byte )
        if ch .isascii ()and (ch .isalnum ()or ch in '*-._'):
            out .append (ch )
        elif byte ==32 :
            out .append ('+')
        else :
            out .append (f'%{byte :02X}')
    return ''.join (out )
def form_encode (pairs )->bytes :
    return '&'.join ((f'{form_urlencode_value (k )}={form_urle
