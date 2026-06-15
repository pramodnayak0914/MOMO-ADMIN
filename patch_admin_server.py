import re

with open('server.py', 'r') as f:
    content = f.read()

# 1. Provide marketing data and growth rules in /api/admin/data
data_query_orig = """                            cur.execute("SELECT amount, COUNT(*) as count FROM transactions GROUP BY amount ORDER BY count DESC LIMIT 5")
                            rows = cur.fetchall()
                            for r in rows:
                                marketing_data['top_amounts'].append({"amount": r['amount'], "count": r['count']})
                    except Exception as e:
                        print(f"Error fetching analytics/metrics: {e}")"""
data_query_new = """                            cur.execute("SELECT amount, COUNT(*) as count FROM transactions GROUP BY amount ORDER BY count DESC LIMIT 5")
                            rows = cur.fetchall()
                            for r in rows:
                                marketing_data['top_amounts'].append({"amount": r['amount'], "count": r['count']})
                                
                            cur.execute("SELECT opid as operator, circle_code as circle, COUNT(*) as search_count FROM marketing_searches GROUP BY opid, circle_code ORDER BY search_count DESC LIMIT 5")
                            marketing_data['popular_plans'] = [dict(r) for r in cur.fetchall()]
                            
                            cur.execute("SELECT value FROM app_config WHERE key = 'referral_rules'")
                            ref_row = cur.fetchone()
                            referral_rules = json.loads(ref_row['value']) if ref_row else {"referrer_reward": 20, "referred_reward": 20}
                            
                            cur.execute("SELECT value FROM app_config WHERE key = 'cashback_rules'")
                            cb_row = cur.fetchone()
                            cashback_rules = json.loads(cb_row['value']) if cb_row else {"first_recharge": 0, "weekend": 0}
                            
                            cur.execute("SELECT value FROM app_config WHERE key = 'loyalty_rules'")
                            loy_row = cur.fetchone()
                            loyalty_rules = json.loads(loy_row['value']) if loy_row else {"silver_min": 0, "gold_min": 500, "platinum_min": 2000}
                            
                            growth_rules = {
                                "referral": referral_rules,
                                "cashback": cashback_rules,
                                "loyalty": loyalty_rules
                            }
                    except Exception as e:
                        print(f"Error fetching analytics/metrics: {e}")
                        growth_rules = {}"""
if data_query_orig in content:
    content = content.replace(data_query_orig, data_query_new)

payload_orig = """                    "fraud_alerts": fraud_list,"""
payload_new = """                    "fraud_alerts": fraud_list,
                    "marketing_data": marketing_data,
                    "growth_rules": growth_rules,"""
if payload_orig in content:
    content = content.replace(payload_orig, payload_new)

# 2. Add /api/admin/growth/save
growth_save_logic = """        elif self.path == '/api/admin/growth/save':
            content_length = int(self.headers.get('Content-Length', 0))
            data = json.loads(self.rfile.read(content_length))
            if data.get('passcode') != ADMIN_PASSCODE: return self._send_json(401, {"error": "Unauthorized"})
            try:
                if DATABASE_URL and psycopg2:
                    conn = psycopg2.connect(DATABASE_URL)
                    cur = conn.cursor()
                    ref_rules = json.dumps(data.get('referral_rules', {}))
                    cb_rules = json.dumps(data.get('cashback_rules', {}))
                    loy_rules = json.dumps(data.get('loyalty_rules', {}))
                    
                    cur.execute("INSERT INTO app_config (key, value) VALUES ('referral_rules', %s) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value", (ref_rules,))
                    cur.execute("INSERT INTO app_config (key, value) VALUES ('cashback_rules', %s) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value", (cb_rules,))
                    cur.execute("INSERT INTO app_config (key, value) VALUES ('loyalty_rules', %s) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value", (loy_rules,))
                    conn.commit()
                    conn.close()
                self._send_json(200, {"success": True})
            except Exception as e:
                self._send_json(500, {"error": str(e)})
            return"""
            
if "elif self.path == '/api/admin/config':" in content:
    content = content.replace("        elif self.path == '/api/admin/config':", growth_save_logic + "\n        elif self.path == '/api/admin/config':")

with open('server.py', 'w') as f:
    f.write(content)
