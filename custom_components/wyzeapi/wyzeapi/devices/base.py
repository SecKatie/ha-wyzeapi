class BaseDevice:
    nick_name: str
    product_model: str
    mac: str
    avaliable: int = 1

    def __init__(self, nick_name, product_model, mac):
        self.nick_name = nick_name
        self.product_model = product_model
        self.mac = mac
