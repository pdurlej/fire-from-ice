//
//  MenuBarItemsUnsupportedNotice.swift
//  Ice
//

import SwiftUI

/// Static notice shown in place of the "Loading menu bar items…" spinner when
/// ``MenuBarPlatformSupport`` reports that item discovery is unsupported on
/// the running macOS (issue #32).
struct MenuBarItemsUnsupportedNotice: View {
    enum Style {
        /// Single line, for compact surfaces such as the IceBar.
        case compact
        /// Stacked, for larger surfaces such as settings and search.
        case large
    }

    static var message: LocalizedStringKey {
        "Arranging menu bar items isn't supported on macOS 27 yet."
    }

    // swiftlint:disable:next force_unwrapping
    static let trackingIssueURL = URL(string: "https://github.com/pdurlej/fire-from-ice/issues/25")!

    let style: Style

    var body: some View {
        switch style {
        case .compact:
            HStack {
                Text(Self.message)
                Link("Learn more", destination: Self.trackingIssueURL)
            }
        case .large:
            VStack(spacing: 8) {
                Text(Self.message)
                    .multilineTextAlignment(.center)
                Link("Learn more", destination: Self.trackingIssueURL)
                    .font(.body)
            }
        }
    }
}
