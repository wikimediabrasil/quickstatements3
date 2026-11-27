class ApiException(Exception):
    def __init__(self, message):
        super(ApiException, self).__init__(message)
        self.message = message


class InvalidPropertyValueType(ApiException):
    def __init__(self, property_id, provided_value_type, needed_value_type):
        self.property_id = property_id
        self.provided_value_type = provided_value_type
        self.needed_value_type = needed_value_type
        message = (
            f"Invalid value type for the property {property_id}: "
            f"'{provided_value_type}' was provided but it needs '{needed_value_type}'."
        )
        return super().__init__(message)


class NonexistantPropertyOrNoDataType(ApiException):
    def __init__(self, property_id):
        self.property_id = property_id
        message = (
            f"The property {property_id} does not exist or "
            "does not have a data type."
        )
        return super().__init__(message)


class NoValueTypeForThisDataType(ApiException):
    def __init__(self, property_id, data_type):
        self.property_id = property_id
        self.data_type = data_type
        message = (
            "There is no value type associated for the "
            f"data type {data_type} of the property {property_id}."
        )
        return super().__init__(message)


class NoStatementsForThatProperty(ApiException):
    def __init__(self, entity_id, property_id):
        self.entity_id = entity_id
        self.property_id = property_id
        message = (
            f"The entity {entity_id} has no statements "
            f"for the property {property_id}"
        )
        return super().__init__(message)


class NoStatementsWithThatValue(ApiException):
    def __init__(self, entity_id, property_id, value):
        self.entity_id = entity_id
        self.property_id = property_id
        self.value = value
        message = (
            f"The entity {entity_id} has no statements "
            f"with value '{value}' for the property {property_id}"
        )
        return super().__init__(message)


class NoStatementsWithThatId(ApiException):
    def __init__(self, entity_id, statement_id):
        self.entity_id = entity_id
        self.statement_id = statement_id
        message = (
            f"The entity {entity_id} has no statements "
            f"with id '{statement_id}'"
        )
        return super().__init__(message)


class NoQualifiers(ApiException):
    def __init__(self):
        return super().__init__("There are no qualifiers with the given value")


class NoReferenceParts(ApiException):
    def __init__(self):
        return super().__init__("There are no reference parts with the given value")


class LastCouldNotBeEvaluated(ApiException):
    def __init__(self):
        return super().__init__("LAST could not be evaluated.")


class UserError(ApiException):
    def __init__(self, status, response_code, response_message, response_json):
        self.status = status
        self.response_code = response_code
        self.response_message = response_message
        self.response_json = response_json
        message = f"Error {status} ('{response_code}'): {response_message}"
        return super().__init__(message)


class ServerError(ApiException):
    def __init__(self, response_json):
        self.response_json = response_json
        message = f"The server failed to process the request: {response_json}"
        return super().__init__(message)


class EntityTypeNotImplemented(ApiException):
    def __init__(self, entity_id):
        message = f"{entity_id}: entity type not supported"
        return super().__init__(message)


class NoToken(ApiException):
    def __init__(self, username):
        self.username = username
        message = f"We don't have an authentication token for the user '{username}'"
        return super().__init__(message)


class UnauthorizedToken(ApiException):
    def __init__(self):
        message = "The token authorization failed."
        return super().__init__(message)


class InternalInvalidState(ApiException):
    def __init__(self, message):
        message = f"There's something wrong in our side: {message}"
        return super().__init__(message)
