import os
from elasticsearch import AsyncElasticsearch

ES_HOST = os.getenv("ES_HOST", "http://localhost:9200")

es_client = AsyncElasticsearch(ES_HOST)

PRODUCTS_INDEX = "products"

PRODUCTS_MAPPING = {
    "mappings": {
        "properties": {
            "product_id":     {"type": "keyword"},
            "title":          {
                "type": "text",
                "analyzer": "standard",
                # fields.keyword cho phép sort/aggregate trên cùng trường
                "fields": {"keyword": {"type": "keyword"}}
            },
            "sub_category":   {"type": "keyword"},
            "main_category":  {"type": "keyword"},
            "brand":          {"type": "keyword"},
            "price":          {"type": "float"},
            "original_price": {"type": "float"},
            "rating":         {"type": "float"},
            "review_count":   {"type": "integer"},
            "image_url":      {"type": "keyword", "index": False},
            "link":           {"type": "keyword", "index": False},
        }
    },
    "settings": {
        "number_of_shards":   1,
        "number_of_replicas": 0,
    }
}
