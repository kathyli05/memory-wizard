#import <Contacts/Contacts.h>
#import <Foundation/Foundation.h>

static NSString *StatusName(CNAuthorizationStatus status) {
    switch (status) {
        case CNAuthorizationStatusAuthorized: return @"authorized";
        case CNAuthorizationStatusDenied: return @"denied";
        case CNAuthorizationStatusRestricted: return @"restricted";
        case CNAuthorizationStatusNotDetermined: return @"not-determined";
#ifdef CNAuthorizationStatusLimited
        case CNAuthorizationStatusLimited: return @"limited";
#endif
        default: return @"unavailable";
    }
}

static void WriteResponse(NSString *status, NSDictionary *results) {
    NSMutableDictionary *response = [@{@"status": status} mutableCopy];
    if (results != nil) response[@"results"] = results;
    NSData *data = [NSJSONSerialization dataWithJSONObject:response options:0 error:nil];
    if (data == nil) exit(1);
    [[NSFileHandle fileHandleWithStandardOutput] writeData:data];
}

static NSString *RequestAccess(void) {
    CNAuthorizationStatus current =
        [CNContactStore authorizationStatusForEntityType:CNEntityTypeContacts];
    if (current != CNAuthorizationStatusNotDetermined) return StatusName(current);

    dispatch_semaphore_t semaphore = dispatch_semaphore_create(0);
    __block NSString *result = @"unavailable";
    [[[CNContactStore alloc] init]
        requestAccessForEntityType:CNEntityTypeContacts
                   completionHandler:^(BOOL granted, NSError *error) {
        (void)granted;
        (void)error;
        result = StatusName(
            [CNContactStore authorizationStatusForEntityType:CNEntityTypeContacts]
        );
        dispatch_semaphore_signal(semaphore);
    }];
    if (dispatch_semaphore_wait(
            semaphore, dispatch_time(DISPATCH_TIME_NOW, 60 * NSEC_PER_SEC)) != 0) {
        return @"unavailable";
    }
    return result;
}

static NSDictionary *ContactResult(CNContact *contact) {
    NSMutableArray *phones = [NSMutableArray array];
    for (CNLabeledValue<CNPhoneNumber *> *value in contact.phoneNumbers) {
        [phones addObject:value.value.stringValue];
    }
    NSMutableArray *emails = [NSMutableArray array];
    for (CNLabeledValue<NSString *> *value in contact.emailAddresses) {
        [emails addObject:value.value];
    }
    return @{
        @"contact_id": contact.identifier,
        @"given_name": contact.givenName,
        @"middle_name": contact.middleName,
        @"family_name": contact.familyName,
        @"nickname": contact.nickname,
        @"organization_name": contact.organizationName,
        @"phone_numbers": phones,
        @"email_addresses": emails,
    };
}

static NSDictionary *Resolve(NSDictionary *request) {
    CNAuthorizationStatus authorization =
        [CNContactStore authorizationStatusForEntityType:CNEntityTypeContacts];
    NSString *status = StatusName(authorization);
    if (![status isEqualToString:@"authorized"] &&
        ![status isEqualToString:@"limited"]) {
        return @{@"status": status, @"results": @{}};
    }

    NSArray *keys = @[
        CNContactIdentifierKey,
        CNContactGivenNameKey,
        CNContactMiddleNameKey,
        CNContactFamilyNameKey,
        CNContactNicknameKey,
        CNContactOrganizationNameKey,
        CNContactPhoneNumbersKey,
        CNContactEmailAddressesKey,
    ];
    CNContactStore *store = [[CNContactStore alloc] init];
    NSMutableDictionary *output = [NSMutableDictionary dictionary];

    for (NSDictionary *lookup in request[@"lookups"] ?: @[]) {
        NSNumber *index = lookup[@"index"];
        NSString *kind = lookup[@"kind"];
        NSString *query = lookup[@"query"];
        NSPredicate *predicate = nil;
        if ([kind isEqualToString:@"phone"]) {
            predicate = [CNContact predicateForContactsMatchingPhoneNumber:
                [CNPhoneNumber phoneNumberWithStringValue:query]];
        } else if ([kind isEqualToString:@"email"]) {
            predicate = [CNContact predicateForContactsMatchingEmailAddress:query];
        }
        if (index == nil || predicate == nil) continue;

        NSError *error = nil;
        NSArray<CNContact *> *contacts =
            [store unifiedContactsMatchingPredicate:predicate keysToFetch:keys error:&error];
        NSMutableArray *matches = [NSMutableArray array];
        if (error == nil) {
            for (CNContact *contact in contacts) [matches addObject:ContactResult(contact)];
        }
        output[index.stringValue] = matches;
    }
    return @{@"status": status, @"results": output};
}

int main(int argc, const char *argv[]) {
    @autoreleasepool {
        NSString *command = argc > 1 ? [NSString stringWithUTF8String:argv[1]] : @"";
        if ([command isEqualToString:@"status"]) {
            WriteResponse(StatusName(
                [CNContactStore authorizationStatusForEntityType:CNEntityTypeContacts]
            ), nil);
        } else if ([command isEqualToString:@"request-access"]) {
            WriteResponse(RequestAccess(), nil);
        } else if ([command isEqualToString:@"resolve"]) {
            NSData *data = [[NSFileHandle fileHandleWithStandardInput] readDataToEndOfFile];
            NSDictionary *request = [NSJSONSerialization JSONObjectWithData:data options:0 error:nil];
            if (![request isKindOfClass:[NSDictionary class]]) {
                WriteResponse(@"unavailable", @{});
            } else {
                NSDictionary *response = Resolve(request);
                WriteResponse(response[@"status"], response[@"results"]);
            }
        } else {
            WriteResponse(@"unavailable", nil);
        }
    }
    return 0;
}
