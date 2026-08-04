from selenium.webdriver.common.by import By
from ..base_page import BasePage


class ContainerDetailsPage(BasePage):
    DROPDOWN_BTN = (By.ID, "associate-dropdown-btn")
    ASSOCIATIONS_BTN = (
        By.CSS_SELECTOR,
        "button[data-testid='benchmark-associations-btn']",
    )
    ASSOCIATIONS_LIST = (By.ID, "benchmark-associations-list")
    ASSOCIATION_CARDS = (
        By.CSS_SELECTOR,
        "div[data-testid='benchmark-associations'] div[data-testid='associated-benchmark-item'] a",
    )
    MANAGE_ACCESS = (By.CSS_SELECTOR, "a[data-testid='manage-access']")

    BENCHMARK = (By.ID, "benchmark")
    EMAILS = (By.ID, "email-input")
    GRANT_ACCESS = (By.ID, "grant-access-btn")
    DELETE_KEYS = (By.ID, "delete-keys-btn")

    def __init__(self, driver, container, benchmark):
        super().__init__(driver)
        self.CONTAINER_BTN = (
            By.XPATH,
            f'//h3//a[@data-testid="cont-name" and contains(text(), "{container}")]',
        )
        self.ASSOCIATE_BTN = (
            By.XPATH,
            f'//div[div[contains(text(), "{benchmark}")]]//button[@data-testid="request-bmk-association"]',
        )

    def request_association(self):
        self.click(self.DROPDOWN_BTN)
        self.click(self.ASSOCIATE_BTN)

    def get_association_cards_titles(self):
        self.click(self.ASSOCIATIONS_BTN)
        associations = self.find(self.ASSOCIATIONS_LIST)
        self.wait_for_visibility_element(associations)
        return [i.text for i in self.driver.find_elements(*self.ASSOCIATION_CARDS)]

    def grant_access(self, benchmark, emails):
        self.select_searchable_entity(self.BENCHMARK, benchmark)
        self.type(self.EMAILS, ",".join(emails) + ",")
        self.click(self.GRANT_ACCESS)

    def delete_keys(self):
        self.click(self.DELETE_KEYS)
