# Define here the models for your scraped items
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/items.html

import scrapy


class SuperScraperItem(scrapy.Item):
    """
    Item class to define the structure of scraped data.
    
    Fields:
        title: The title/name of the item
        price: The price of the item (will be stored as float)
        description: A short description of the item
        image_url: The full URL of the item's image
        stock_availability: Whether the item is in stock (boolean)
        sku: The Stock Keeping Unit identifier
    """
    title = scrapy.Field()
    price = scrapy.Field()
    description = scrapy.Field()
    image_url = scrapy.Field()
    stock_availability = scrapy.Field()
    sku = scrapy.Field()
