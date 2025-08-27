# TODO: Refactor
# from graphql import GraphQLError
# from rest_framework.test import APIClient

# from applications.graphQL.schema import schema
# from rest_framework.test import APIRequestFactory, APITestCase, force_authenticate


# class GraphQLInsultTestCase(APITestCase):
#     """Test cases for GraphQL insult queries."""
#     @classmethod
#     def setUpTestData(cls):
#         """Set up for GraphQL tests."""
#         super().setUp()
#         self.client = APIClient(schema)
#         cls.active_insults = [
#             cls.(
#                 content="Test insult 1", category=GraphQLInsultTestCase.test_category
#             ),
#             cls.create_insult(
#                 content="Test insult 2", category=GraphQLInsultTestCase.test_category
#             ),
#         ]
#         cls.inactive_insult = self.create_insult(
#             content="Test insult 3",
#             category=GraphQLInsultTestCase.test_category,
#             status="I",
#         )

#     def test_random_insult(self):
#         """Test random insult query with different categories."""
#         test_cases = [
#             ("F", True),  # Category with insults
#             ("Y", False),  # Category without active insults
#             (None, True),  # No category filter
#         ]

#         for category, should_have_content in test_cases:
#             query = """
#                 query {
#                     randomInsult(category: "%s") {
#                         content
#                     }
#                 }
#             """ % (
#                 category or ""
#             )

#             result = self.client.execute(query)
#             if should_have_content:
#                 self.assertIn(
#                     result["data"]["randomInsult"]["content"],
#                     ["Test insult 1", "Test insult 2"],
#                 )
#             else:
#                 self.assertIsNone(result["data"]["randomInsult"])

#     def test_insult_by_id(self):
#         """Test fetching insult by ID."""
#         test_cases = [(1, True), (999, False)]  # Existing insult  # Non-existent insult

#         for insult_id, should_exist in test_cases:
#             query = (
#                 """
#                 query {
#                     insultById(id: %s) {
#                         content
#                     }
#                 }
#             """
#                 % insult_id
#             )

#             try:
#                 result = self.client.execute(query)
#                 if should_exist:
#                     self.assertIsNotNone(result["data"]["insultById"])
#                 else:
#                     self.assertIsNone(result["data"]["insultById"])
#             except GraphQLError:
#                 self.assertFalse(should_exist)


# class InsultClassificationTestCase(BaseTestCase):
#     """Test cases for insult classification features."""

#     def setUp(self):
#         """Set up for classification tests."""
#         super().setUp()
#         self.nsfw_insult = self.create_insult(nsfw=True)
#         self.sfw_insults = [
#             self.create_insult(nsfw=False),
#             self.create_insult(nsfw=False),
#         ]

#     def test_insult_classification(self):
#         """Test insult classification queries."""
#         query = """
#             query($nsfw: Boolean!, $offset: Int!, $limit: Int!) {
#                 insultsByClassification(nsfw: $nsfw, offset: $offset, limit: $limit) {
#                     totalCount
#                     items {
#                         content
#                     }
#                 }
#             }
#         """

#         test_cases = [
#             (True, 0, 10, 1),  # NSFW insults
#             (False, 0, 10, 2),  # SFW insults
#             (True, 0, 1, 1),  # NSFW with limit
#             (False, 1, 1, 2),  # SFW with offset and limit
#         ]

#         for nsfw, offset, limit, expected_count in test_cases:
#             variables = {"nsfw": nsfw, "offset": offset, "limit": limit}
#             result = self.client.execute(query, variables=variables)
#             self.assertEqual(
#                 result["data"]["insultsByClassification"]["totalCount"], expected_count
#             )
