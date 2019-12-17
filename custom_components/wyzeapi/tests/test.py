from .secrets import *
from ..wyzeapi.wyzeapi_exceptions import *
from ..wyzeapi.wyzeapi import WyzeApi

def TestAccessTokenError():
	print("Test: TestAccessTokenError")

	wyze = WyzeApi(username, password, no_save=True)

	bulbs = wyze.list_bulbs()
	# Kill access token

	wyze._access_token = "Killed"

	try:
		wyze.list_bulbs()
		assert(True)
	except WyzeApiError:
		print("SUCCESS")
		return

	print("ERROR")

def TestBadPassword():
	print("Test: TestBadPassword")

	try:
		wyze = WyzeApi(username, "BadPassword", no_save=True)
	except WyzeApiError:
		print("SUCCESS")
		return

	print("ERROR")

def TestTurnOffBulbs():
	print("Test: TestTurnOffBulbs")

	wyze = WyzeApi(username, password, no_save=True)

	bulbs = wyze.list_bulbs()

	for bulb in bulbs:
		bulb.turn_off()

	print("SUCCESS")

def TestTurnOnBulbs():
	print("Test: TestTurnOnBulbs")

	wyze = WyzeApi(username, password, no_save=True)

	bulbs = wyze.list_bulbs()

	for bulb in bulbs:
		bulb.turn_on()

	print("SUCCESS")


if __name__ == '__main__':
	TestAccessTokenError()
	TestBadPassword()
	TestTurnOffBulbs()
	#TestTurnOnBulbs()
