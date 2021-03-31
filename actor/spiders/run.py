import scrapy
import apify
import re
import requests
from scrapy.spiders import SitemapSpider
import json


class CrutchfieldSpider(SitemapSpider):
    name = 'crutchfield'
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 11_0_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.88 Safari/537.36',
    }
    sitemap_urls = ['https://www.crutchfield.com/sitemap-cameraproduct.xml',
                    'https://www.crutchfield.com/sitemap-homeproduct.xml',
                    'https://www.crutchfield.com/sitemap-portableproduct.xml',
                    'https://www.crutchfield.com/sitemap-proaudioproduct.xml',
                    'https://www.crutchfield.com/sitemap-tvproduct.xml']

    def parse(self, response):
        """
        This method parse products pages and get all the required data
        """

        product_id = re.search('/p_(.*?)/', response.url).group(1)
        product_reviews, avg_rating = self.get_product_review(product_id)
        product_object = {'page_url': response.url, "product_number": product_id}

        title = response.xpath('//h1[@class="prod-title"]/text()').get()
        sub_title = response.xpath('//h2[@class="prod-sub-title"]/text()').get()
        categories = response.xpath('//ol[@class="breadcrumb"]/li/a/text()').getall()
        vendor = response.xpath('(//img[@class="img-fluid"])[1]/@alt').get()
        original_price = response.xpath('(//div[@class="product-pricing js-productPricing"])[1]//span[@class="original-price"]/text()').getall()
        price = response.xpath('(//div[@class="product-pricing js-productPricing"])[1]//div[@class="price js-price"]//text()').getall()

        regular_price = None
        sale_price = None

        if not original_price and not price:
            regular_price = None
            sale_price = None

        elif original_price and price:
            regular_price = ''.join(original_price)
            sale_price = ''.join(price)

        elif price and not sale_price:
            regular_price = ''.join(price)

        tags = response.xpath('//div[@class="related-searches-scroll"]/a/text()').getall()
        stock_description = response.xpath('(//div[@class="stock-eta-desc"])[1]/span/text()').get()

        in_stock = False
        if not stock_description:
            in_stock = False
        elif stock_description == 'In stock' or stock_description == 'Low stock':
            in_stock = True

        images_urls = response.xpath('//div[@id="js-productThumbCarousel"]/button/img/@data-src').getall()

        images_urls = [url.replace('//', '').replace('fixedscale/90/90', 'trim/620/378') for url in images_urls]
        overview_about = (''.join(response.xpath('//div[@class="row our-take"]//text()').getall())).replace('READ LESS', '')
        overview_about_raw_html = response.xpath('//div[@class="row our-take"]//*').get()

        overview_highlights = []
        h2_heading = response.xpath('//div[@class="highlight-wrapper"]/h2/text()').get()
        h2_points = response.xpath('//div[@class="highlight-wrapper"]/h2/following-sibling::ul[1]//text()').getall()
        overview_highlights.append({
            'heading': h2_heading,
            'points': h2_points
        })

        h5_headings = response.xpath('//div[@class="highlight-wrapper"]/h5')

        for h in h5_headings:
            overview_highlights.append({
                'heading': h.xpath('./text()').get(),
                'points': h.xpath('./following-sibling::ul[1]//text()').getall()
            })

        overview_highlights_raw_html = response.xpath('//div[@id="hightlightWrapper"]//*').get()
        overview_whatsintheBox = response.xpath('//div[@class="whatsInTheBox sideBlock"]//li/text()').getall()
        overview_whatsintheBox_raw_html = response.xpath('//div[@class="col-12 col-lg-5 whats-in-the-box"]//*').get()

        features = response.xpath('//div[@id="SpecsWrapper"]//tbody/tr')
        detail_features = {}
        for f in features:
            detail_features.update({
                (''.join(f.xpath('./td[1]//text()').getall())).strip(): (
                    ''.join(f.xpath('./td[2]//text()').getall())).strip()
            })

        q_and_a = response.xpath('//div[contains(@class, "card qa-question")]')
        q_and_a_array = []

        for q_a in q_and_a:
            question = {
                'text': (q_a.xpath('.//a//div[@class="question-symbol"]/following-sibling::text()[1]').get()).strip(),
                'user_and_date': q_a.xpath('.//a//div[@class="question-symbol"]/following-sibling::text()[1]/following-sibling::div/text()').get()

            }
            answers = []
            answers_blocks = q_a.xpath('.//div[@class="answer-block"]')

            for block in answers_blocks:
                answers.append({
                    'text': (block.xpath('./text()[1]').get()).strip(),
                    'user_and_date': block.xpath('./text()[1]/following-sibling::div/text()').get()
                })

            q_and_a_array.append({
                'question': question,
                'answers': answers,
            })

        product_object.update({
            'title': title,
            'sub_title': sub_title,
            'categories': categories,
            'vendor': vendor,
            'regular_price': regular_price.strip() if regular_price else None,
            'sale_price': sale_price.strip() if sale_price else None,
            'tags': tags,
            'in_stock': in_stock,
            'images_urls': images_urls,
            'overview_about': overview_about.strip(),
            'overview_about_raw_html': overview_about_raw_html,
            'overview_highlights': overview_highlights,
            'overview_highlights_raw_html': overview_highlights_raw_html,
            'overview_whatsintheBox': overview_whatsintheBox,
            'overview_whatsintheBox_raw_html': overview_whatsintheBox_raw_html,
            'detail_features': detail_features,
            'q_and_a': q_and_a_array,
            'reviews_average': avg_rating,
            'reviews': product_reviews
        })
        apify.pushData(product_object)

    def get_product_review(self, product_id):
        """
        This method takes a product_id and returns array of reviews objects
        """

        avg_rating = 0

        reviews = []
        page = 1
        while True:
            params = (
                ('i', product_id),
                ('revp', page)
            )
            response = json.loads(
                (requests.get('https://www.crutchfield.com/handlers/product/item/reviews.ashx', params=params)).text)

            if not response['ReviewList']:
                break

            for r_object in response['ReviewList']:
                reviews.append({
                    "Title": r_object.get("Title").replace('\n', '').replace('\r', ''),
                    "Rating": r_object.get("Rating"),
                    "ReviewDateTime": r_object.get("ReviewDateTime"),
                    "Location": r_object.get("Location"),
                    "Comment": r_object.get("Comment").replace('\n', '').replace('\r', ''),
                    "Pros": r_object.get("Pros").replace('\n', '').replace('\r', ''),
                    "Cons": r_object.get("Cons").replace('\n', '').replace('\r', ''),
                    "YesCount": r_object.get("YesCount"),
                    "NoCount": r_object.get("NoCount"),
                    "TotalHelpfulCount": r_object.get("TotalHelpfulCount"),
                    "HelpfulCountDisplay": r_object.get("HelpfulCountDisplay"),
                    "IsVerifiedPurchase": r_object.get("IsVerifiedPurchase"),

                })

            page = page + 1

        for rating in response['RatingList']:
            avg_rating = avg_rating + rating['Rating'] * rating['Count']
        if response['TotalRecordCount'] > 0:
            avg_rating = avg_rating / response['TotalRecordCount']
        else:
            avg_rating = None
        return reviews, avg_rating
