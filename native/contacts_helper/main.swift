import Contacts
import Foundation

struct Lookup: Decodable {
    let index: Int
    let kind: String
    let query: String
}

struct Request: Decodable {
    let lookups: [Lookup]?
}

struct ContactResult: Encodable {
    let contact_id: String
    let given_name: String
    let middle_name: String
    let family_name: String
    let nickname: String
    let organization_name: String
    let phone_numbers: [String]
    let email_addresses: [String]
}

struct Response: Encodable {
    let status: String
    let results: [String: [ContactResult]]?
}

func statusName(_ status: CNAuthorizationStatus) -> String {
    switch status {
    case .authorized:
        return "authorized"
    case .denied:
        return "denied"
    case .restricted:
        return "restricted"
    case .notDetermined:
        return "not-determined"
    case .limited:
        return "limited"
    @unknown default:
        return "unavailable"
    }
}

func writeResponse(_ response: Response) {
    guard let data = try? JSONEncoder().encode(response) else {
        exit(1)
    }
    FileHandle.standardOutput.write(data)
}

func requestAccess() -> String {
    let current = CNContactStore.authorizationStatus(for: .contacts)
    if current != .notDetermined {
        return statusName(current)
    }

    let semaphore = DispatchSemaphore(value: 0)
    var result = "unavailable"
    CNContactStore().requestAccess(for: .contacts) { _, _ in
        result = statusName(CNContactStore.authorizationStatus(for: .contacts))
        semaphore.signal()
    }
    if semaphore.wait(timeout: .now() + 60) == .timedOut {
        return "unavailable"
    }
    return result
}

func contactResult(_ contact: CNContact) -> ContactResult {
    ContactResult(
        contact_id: contact.identifier,
        given_name: contact.givenName,
        middle_name: contact.middleName,
        family_name: contact.familyName,
        nickname: contact.nickname,
        organization_name: contact.organizationName,
        phone_numbers: contact.phoneNumbers.map { $0.value.stringValue },
        email_addresses: contact.emailAddresses.map { $0.value as String }
    )
}

func resolve(_ request: Request) -> Response {
    let authorization = CNContactStore.authorizationStatus(for: .contacts)
    let status = statusName(authorization)
    guard status == "authorized" || status == "limited" else {
        return Response(status: status, results: [:])
    }

    let keys: [CNKeyDescriptor] = [
        CNContactIdentifierKey as CNKeyDescriptor,
        CNContactGivenNameKey as CNKeyDescriptor,
        CNContactMiddleNameKey as CNKeyDescriptor,
        CNContactFamilyNameKey as CNKeyDescriptor,
        CNContactNicknameKey as CNKeyDescriptor,
        CNContactOrganizationNameKey as CNKeyDescriptor,
        CNContactPhoneNumbersKey as CNKeyDescriptor,
        CNContactEmailAddressesKey as CNKeyDescriptor,
    ]
    let store = CNContactStore()
    var output: [String: [ContactResult]] = [:]

    for lookup in request.lookups ?? [] {
        let predicate: NSPredicate
        if lookup.kind == "phone" {
            predicate = CNContact.predicateForContacts(
                matching: CNPhoneNumber(stringValue: lookup.query)
            )
        } else if lookup.kind == "email" {
            predicate = CNContact.predicateForContacts(matchingEmailAddress: lookup.query)
        } else {
            output[String(lookup.index)] = []
            continue
        }

        do {
            output[String(lookup.index)] = try store
                .unifiedContacts(matching: predicate, keysToFetch: keys)
                .map(contactResult)
        } catch {
            output[String(lookup.index)] = []
        }
    }
    return Response(status: status, results: output)
}

let command = CommandLine.arguments.dropFirst().first ?? ""
switch command {
case "status":
    writeResponse(Response(
        status: statusName(CNContactStore.authorizationStatus(for: .contacts)),
        results: nil
    ))
case "request-access":
    writeResponse(Response(status: requestAccess(), results: nil))
case "resolve":
    let data = FileHandle.standardInput.readDataToEndOfFile()
    guard let request = try? JSONDecoder().decode(Request.self, from: data) else {
        writeResponse(Response(status: "unavailable", results: [:]))
        exit(0)
    }
    writeResponse(resolve(request))
default:
    writeResponse(Response(status: "unavailable", results: nil))
}
