from configparser import ConfigParser

def parseConfig():
	config = ConfigParser()
	config.read('wyzeconfig.ini')

	try:
		access_token = config.get('auth', 'access_token')
		device_id = config.get('auth', 'device_id')

		return (device_id, access_token)
	except:
		return (None, None)

def updateConfig(device_id, access_token):
	config = ConfigParser()
	config.read('wyzeconfig.ini')
	config.add_section('auth')
	config.set('auth', 'access_token', str(access_token))
	config.set('auth', 'device_id', str(device_id))
	with open('wyzeconfig.ini', 'w') as f:
		config.write(f)
