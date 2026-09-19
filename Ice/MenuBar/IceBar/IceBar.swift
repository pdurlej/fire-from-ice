//
//  IceBar.swift
//  Ice
//

import Combine
import OSLog
import SwiftUI

// MARK: - IceBarPanel

final class IceBarPanel: NSPanel {
    /// The shared app state.
    private weak var appState: AppState?

    /// Manager for the Ice Bar's color.
    private let colorManager = IceBarColorManager()

    /// The currently displayed section.
    private(set) var currentSection: MenuBarSection.Name?

    /// Storage for internal observers.
    private var cancellables = Set<AnyCancellable>()

    /// Monitors that dismiss the panel, active only while it is shown.
    private var dismissMonitors = [EventMonitor]()

    /// Creates a new Ice Bar panel.
    init() {
        super.init(
            contentRect: .zero,
            styleMask: [.nonactivatingPanel, .fullSizeContentView, .borderless],
            backing: .buffered,
            defer: false
        )
        self.title = "Ice Bar"
        self.titlebarAppearsTransparent = true
        self.isMovableByWindowBackground = true
        self.allowsToolTipsWhenApplicationIsInactive = true
        self.isFloatingPanel = true
        self.animationBehavior = .none
        self.backgroundColor = .clear
        self.hasShadow = false
        self.level = .mainMenu + 1
        self.collectionBehavior = [.fullScreenAuxiliary, .ignoresCycle, .moveToActiveSpace]
    }

    /// Sets up the panel.
    func performSetup(with appState: AppState) {
        self.appState = appState
        configureCancellables()
        colorManager.performSetup(with: self)
    }

    /// Configures the internal observers.
    private func configureCancellables() {
        var c = Set<AnyCancellable>()

        // Hide the panel when the active space or screen parameters change.
        Publishers.Merge(
            NSWorkspace.shared.notificationCenter.publisher(for: NSWorkspace.activeSpaceDidChangeNotification),
            NotificationCenter.default.publisher(for: NSApplication.didChangeScreenParametersNotification)
        )
        .sink { [weak self] _ in
            self?.hide()
        }
        .store(in: &c)

        // Update the panel's origin whenever its size changes.
        publisher(for: \.frame).map(\.size)
            .removeDuplicates()
            .sink { [weak self] _ in
                guard let self, let screen else {
                    return
                }
                updateOrigin(for: screen)
            }
            .store(in: &c)

        if let controlItem = appState?.menuBarManager.controlItem(withName: .hidden) {
            // Use the hidden control item's frame to determine if the menu bar
            // is hidden. Hide the panel if so.
            controlItem.$frame
                .combineLatest(controlItem.$screen)
                .throttle(for: 0.1, scheduler: DispatchQueue.main, latest: true)
                .sink { [weak self] (frame, screen) in
                    guard let self else {
                        return
                    }

                    guard let frame, let screen else {
                        hide()
                        return
                    }

                    // Icon is not vertically visible. We can infer that the
                    // menu bar is hidden.
                    if frame.maxY > screen.frame.maxY {
                        hide()
                    }
                }
                .store(in: &c)
        }

        cancellables = c
    }

    /// Updates the panel's frame origin for display on the given screen.
    private func updateOrigin(for screen: NSScreen) {
        guard let appState else {
            return
        }

        func getOrigin(for iceBarLocation: IceBarLocation) -> CGPoint {
            let menuBarHeight = screen.getMenuBarHeight() ?? 0
            let originY = ((screen.frame.maxY - 1) - menuBarHeight) - frame.height

            var originForRightOfScreen: CGPoint {
                CGPoint(x: screen.frame.maxX - frame.width, y: originY)
            }

            switch iceBarLocation {
            case .dynamic:
                if appState.hidEventManager.isMouseInsideEmptyMenuBarSpace(appState: appState, screen: screen) {
                    return getOrigin(for: .mousePointer)
                }
                return getOrigin(for: .iceIcon)
            case .mousePointer:
                guard let location = MouseHelpers.locationAppKit else {
                    return getOrigin(for: .iceIcon)
                }

                let lowerBound = screen.frame.minX
                let upperBound = screen.frame.maxX - frame.width

                guard lowerBound <= upperBound else {
                    return originForRightOfScreen
                }

                return CGPoint(x: (location.x - frame.width / 2).clamped(to: lowerBound...upperBound), y: originY)
            case .iceIcon:
                let lowerBound = screen.frame.minX
                let upperBound = screen.frame.maxX - frame.width

                guard
                    lowerBound <= upperBound,
                    let controlItem = appState.itemManager.itemCache.managedItems.first(matching: .visibleControlItem),
                    // Bridging API is more reliable than controlItem.frame in some
                    // cases (like if the item is offscreen).
                    let itemBounds = Bridging.getWindowBounds(for: controlItem.windowID)
                else {
                    return originForRightOfScreen
                }

                return CGPoint(x: (itemBounds.midX - frame.width / 2).clamped(to: lowerBound...upperBound), y: originY)
            }
        }

        setFrameOrigin(getOrigin(for: appState.settings.general.iceBarLocation))
    }

    /// Shows the panel on the given screen, displaying the given
    /// menu bar section.
    func show(section: MenuBarSection.Name, on screen: NSScreen) async {
        guard let appState else {
            return
        }

        // IMPORTANT: We must set the navigation state and current section
        // before updating the caches.
        appState.navigationState.isIceBarPresented = true
        currentSection = section

        // One second was not enough for a cold cache: the first open after a
        // launch has to enumerate every item and render an image for each.
        // When the timeout cancelled that work, the bar came up empty. Do not
        // stretch this much further either — the panel does not appear until
        // the wait is over, and the content view now reloads on its own.
        let cacheTask = Task(timeout: .milliseconds(1500)) {
            await appState.itemManager.cacheItemsIfNeeded()
            await appState.imageCache.updateCache()
        }

        do {
            try await cacheTask.value
        } catch {
            Logger.default.error("Cache update failed when showing IceBarPanel - \(error)")
        }

        contentView = IceBarHostingView(
            appState: appState,
            colorManager: colorManager,
            screen: screen,
            section: section
        )

        // `updateOrigin` derives the origin from the panel's own height and
        // width. SwiftUI lays the hosting view out on the next pass, so without
        // forcing it here the first origin is computed from the previous
        // content's size: the bar appears offset and then jumps into place once
        // the frame observer catches up.
        contentView?.layoutSubtreeIfNeeded()

        updateOrigin(for: screen)

        // Color manager must be updated after updating the panel's origin,
        // but before it is shown.
        //
        // Color manager handles frame changes automatically, but does so on
        // the main queue, so we need to update manually once before showing
        // the panel to prevent the color from flashing.
        colorManager.updateAllProperties(with: frame, screen: screen)

        orderFrontRegardless()

        startDismissMonitors()
    }

    /// Starts the monitors that dismiss the panel.
    ///
    /// Until these existed, the only thing that closed the Ice Bar after a
    /// click elsewhere was the smart rehide strategy, which is off unless the
    /// user picked it and ignores clicks on the desktop, on untitled windows
    /// and on background apps. Every floating panel is expected to go away when
    /// it is clicked past or escaped, so handle both here regardless of the
    /// rehide settings.
    private func startDismissMonitors() {
        stopDismissMonitors()

        let clickMonitor = EventMonitor.universal(
            for: [.leftMouseDown, .rightMouseDown, .otherMouseDown]
        ) { [weak self] event in
            guard let self, isVisible else {
                return event
            }
            // Clicks inside the panel are the item clicks; they dismiss it
            // themselves once the click has been routed to the item.
            if event.window === self {
                return event
            }
            let location = NSEvent.mouseLocation
            if frame.contains(location) {
                return event
            }
            // The menu bar owns its own clicks: the Ice icon toggles the
            // section, and empty space is handled by the show-on-click
            // machinery. Dismissing here would race those and reopen the bar.
            let screen = NSScreen.screens.first { $0.frame.contains(location) } ?? NSScreen.main
            if let screen, location.y >= screen.visibleFrame.maxY {
                return event
            }
            hide()
            return event
        }

        let keyMonitor = EventMonitor.universal(for: .keyDown) { [weak self] event in
            guard let self, isVisible else {
                return event
            }
            guard event.keyCode == 53 else { // Escape
                return event
            }
            hide()
            return nil
        }

        for monitor in [clickMonitor, keyMonitor] {
            monitor.start()
        }
        dismissMonitors = [clickMonitor, keyMonitor]
    }

    /// Stops the monitors that dismiss the panel.
    private func stopDismissMonitors() {
        for monitor in dismissMonitors {
            monitor.stop()
        }
        dismissMonitors.removeAll()
    }

    /// Hides the panel.
    func hide() {
        if
            let name = currentSection,
            let section = appState?.menuBarManager.section(withName: name)
        {
            section.hide()
        }
        close()
    }

    override func close() {
        stopDismissMonitors()
        super.close()
        contentView = nil
        currentSection = nil
        appState?.navigationState.isIceBarPresented = false
    }
}

// MARK: - IceBarHostingView

private final class IceBarHostingView: NSHostingView<IceBarContentView> {
    override var safeAreaInsets: NSEdgeInsets { NSEdgeInsets() }

    init(
        appState: AppState,
        colorManager: IceBarColorManager,
        screen: NSScreen,
        section: MenuBarSection.Name
    ) {
        let rootView = IceBarContentView(
            appState: appState,
            colorManager: colorManager,
            itemManager: appState.itemManager,
            imageCache: appState.imageCache,
            menuBarManager: appState.menuBarManager,
            screen: screen,
            section: section
        )
        super.init(rootView: rootView)
    }

    @available(*, unavailable)
    required init?(coder: NSCoder) {
        fatalError("init(coder:) has not been implemented")
    }

    @available(*, unavailable)
    required init(rootView: IceBarContentView) {
        fatalError("init(rootView:) has not been implemented")
    }

    override func acceptsFirstMouse(for event: NSEvent?) -> Bool {
        return true
    }
}

// MARK: - IceBarContentView

private struct IceBarContentView: View {
    @ObservedObject var appState: AppState
    @ObservedObject var colorManager: IceBarColorManager
    @ObservedObject var itemManager: MenuBarItemManager
    @ObservedObject var imageCache: MenuBarItemImageCache
    @ObservedObject var menuBarManager: MenuBarManager
    @State private var frame = CGRect.zero
    @State private var scrollIndicatorsFlashTrigger = 0
    @State private var loadingFailed = false
    @State private var reloadToken = 0

    let screen: NSScreen
    let section: MenuBarSection.Name

    private var items: [MenuBarItem] {
        itemManager.itemCache.managedItems(for: section)
    }

    private var configuration: MenuBarAppearanceConfigurationV2 {
        appState.appearanceManager.configuration
    }

    private var horizontalPadding: CGFloat {
        if #available(macOS 26.0, *) {
            return 3
        }
        return configuration.hasRoundedShape ? 7 : 5
    }

    private var verticalPadding: CGFloat {
        if #available(macOS 26.0, *) {
            return screen.hasNotch && configuration.hasRoundedShape ? 2 : 0
        }
        return screen.hasNotch ? 0 : 2
    }

    private var contentHeight: CGFloat? {
        guard let menuBarHeight = screen.getMenuBarHeight() else {
            return nil
        }
        if configuration.shapeKind != .noShape && configuration.isInset && screen.hasNotch {
            return menuBarHeight - appState.appearanceManager.menuBarInsetAmount * 2
        }
        return menuBarHeight
    }

    private var clipShape: some InsettableShape {
        if configuration.hasRoundedShape {
            RoundedRectangle(cornerRadius: frame.height / 2, style: .circular)
        } else if #available(macOS 26.0, *) {
            RoundedRectangle(cornerRadius: frame.height / 4, style: .continuous)
        } else {
            RoundedRectangle(cornerRadius: frame.height / 5, style: .continuous)
        }
    }

    private var shadowOpacity: CGFloat {
        configuration.current.hasShadow ? 0.5 : 0.33
    }

    var body: some View {
        ZStack {
            content
                .frame(height: contentHeight)
                .padding(.horizontal, horizontalPadding)
                .padding(.vertical, verticalPadding)
                .menuBarItemContainer(appState: appState, colorInfo: colorManager.colorInfo)
                .foregroundStyle(colorManager.colorInfo?.color.brightness ?? 0 > 0.67 ? .black : .white)
                .clipShape(clipShape)
                .shadow(color: .black.opacity(shadowOpacity), radius: 2.5)

            if configuration.current.hasBorder {
                clipShape
                    .inset(by: configuration.current.borderWidth / 2)
                    .stroke(lineWidth: configuration.current.borderWidth)
                    .foregroundStyle(Color(cgColor: configuration.current.borderColor))
            }
        }
        .padding(5)
        .frame(maxWidth: screen.frame.width)
        .fixedSize()
        .onFrameChange(update: $frame)
    }

    /// The message shown when items could not be loaded, with a way out.
    private var retryMessage: some View {
        HStack(spacing: 8) {
            Text("Menu bar items couldn't be loaded.")

            Button {
                loadingFailed = false
                reloadToken += 1
            } label: {
                Text("Try Again")
            }
            .buttonStyle(.plain)
            .foregroundStyle(.link)
        }
        .padding(.horizontal, 10)
    }

    /// Rebuilds the item cache until it holds something, or gives up.
    private func loadItemsUntilAvailable() async {
        for attempt in 1...5 {
            guard itemManager.itemCache.managedItems.isEmpty else {
                loadingFailed = false
                return
            }
            await itemManager.cacheItemsRegardless()
            await imageCache.updateCache()
            guard itemManager.itemCache.managedItems.isEmpty else {
                loadingFailed = false
                return
            }
            try? await Task.sleep(for: .milliseconds(200 * attempt))
        }
        loadingFailed = itemManager.itemCache.managedItems.isEmpty
    }

    @ViewBuilder
    private var content: some View {
        if !ScreenCapture.cachedCheckPermissions() {
            HStack {
                Text("The Ice Bar requires screen recording permissions.")

                Button {
                    menuBarManager.section(withName: section)?.hide()
                    appState.navigationState.settingsNavigationIdentifier = .advanced
                    appState.activate(withPolicy: .regular)
                    appState.openWindow(.settings)
                } label: {
                    Text("Open Ice Settings")
                }
                .buttonStyle(.plain)
                .foregroundStyle(.link)
            }
            .padding(.horizontal, 10)
        } else if menuBarManager.isMenuBarHiddenBySystemUserDefaults {
            Text("Ice cannot display menu bar items for automatically hidden menu bars")
                .padding(.horizontal, 10)
        } else if itemManager.itemCache.managedItems.isEmpty {
            // A spinner next to "Loading menu bar items…" reads as a hang the
            // moment it lasts longer than an instant, and this one used to last
            // forever. Placeholders say the same thing in the shape of the bar
            // that is coming, and the failure state offers the retry instead of
            // leaving the user to guess.
            Group {
                if loadingFailed {
                    retryMessage
                } else {
                    IceBarPlaceholderItems()
                }
            }
            // Nothing else retries: if the cache is empty when the bar opens,
            // it stays empty unless someone asks again.
            .task(id: reloadToken) {
                await loadItemsUntilAvailable()
            }
        } else if imageCache.cacheFailed(for: section) {
            retryMessage
        } else {
            ScrollView(.horizontal) {
                HStack(spacing: 0) {
                    ForEach(items, id: \.windowID) { item in
                        IceBarItemView(
                            imageCache: imageCache,
                            itemManager: itemManager,
                            menuBarManager: menuBarManager,
                            item: item,
                            section: section
                        )
                    }
                }
            }
            // Comparing two CGFloats for equality left scrolling disabled on a
            // bar that had in fact been clamped to the screen width, stranding
            // the items that did not fit. Allow for rounding.
            .environment(\.isScrollEnabled, frame.width >= screen.frame.width - 1)
            .defaultScrollAnchor(.trailing)
            .scrollIndicatorsFlash(trigger: scrollIndicatorsFlashTrigger)
            .task {
                scrollIndicatorsFlashTrigger += 1
            }
        }
    }
}

// MARK: - IceBarPlaceholderItems

/// Stand-ins shown in the shape of menu bar items while the caches fill.
private struct IceBarPlaceholderItems: View {
    @State private var isPulsing = false

    var body: some View {
        HStack(spacing: 6) {
            ForEach(0..<4, id: \.self) { _ in
                RoundedRectangle(cornerRadius: 5, style: .continuous)
                    .fill(.primary.opacity(isPulsing ? 0.2 : 0.08))
                    .frame(width: 18, height: 18)
            }
        }
        .padding(.horizontal, 8)
        .animation(.easeInOut(duration: 0.8).repeatForever(autoreverses: true), value: isPulsing)
        .onAppear {
            isPulsing = true
        }
        .accessibilityLabel("Loading menu bar items")
    }
}

// MARK: - IceBarItemView

private struct IceBarItemView: View {
    @ObservedObject var imageCache: MenuBarItemImageCache
    @ObservedObject var itemManager: MenuBarItemManager
    @ObservedObject var menuBarManager: MenuBarManager

    @State private var isHovering = false
    @State private var isPressed = false

    let item: MenuBarItem
    let section: MenuBarSection.Name

    private var leftClickAction: () -> Void {
        return { [weak itemManager, weak menuBarManager] in
            guard let itemManager, let menuBarManager else {
                return
            }
            menuBarManager.section(withName: section)?.hide()
            let windowID = item.windowID
            Task {
                try await Task.sleep(for: .milliseconds(25))
                // `isWindowOnScreen` is a synchronous window-server query
                // (SLSGetOnScreenWindowCount); run it off the main thread so a
                // busy window server can't freeze this click (fire.10.4.1).
                let onScreen = await Task.detached { Bridging.isWindowOnScreen(windowID) }.value
                if onScreen {
                    try await itemManager.click(item: item, with: .left)
                } else {
                    await itemManager.temporarilyShow(item: item, clickingWith: .left)
                }
            }
        }
    }

    private var rightClickAction: () -> Void {
        return { [weak itemManager, weak menuBarManager] in
            guard let itemManager, let menuBarManager else {
                return
            }
            menuBarManager.section(withName: section)?.hide()
            let windowID = item.windowID
            Task {
                try await Task.sleep(for: .milliseconds(25))
                // Off-main window-server query — see leftClickAction (fire.10.4.1).
                let onScreen = await Task.detached { Bridging.isWindowOnScreen(windowID) }.value
                if onScreen {
                    try await itemManager.click(item: item, with: .right)
                } else {
                    await itemManager.temporarilyShow(item: item, clickingWith: .right)
                }
            }
        }
    }

    private var image: NSImage? {
        guard let cachedImage = imageCache.images[item.tag] else {
            return nil
        }
        return cachedImage.nsImage
    }

    var body: some View {
        if let image {
            Image(nsImage: image)
                .contentShape(Rectangle())
                .background {
                    // The real menu bar highlights an item while it is pressed.
                    // Without an equivalent here, a click that is still being
                    // routed to the item looks like a click that did nothing.
                    RoundedRectangle(cornerRadius: 5, style: .continuous)
                        .fill(.primary.opacity(highlightOpacity))
                        .padding(.vertical, 2)
                        .animation(.easeOut(duration: 0.1), value: highlightOpacity)
                }
                .overlay {
                    IceBarItemClickView(
                        item: item,
                        leftClickAction: leftClickAction,
                        rightClickAction: rightClickAction,
                        isHovering: $isHovering,
                        isPressed: $isPressed
                    )
                }
                .accessibilityLabel(item.displayName)
                .accessibilityAction(named: "left click", leftClickAction)
                .accessibilityAction(named: "right click", rightClickAction)
        }
    }

    private var highlightOpacity: Double {
        if isPressed {
            return 0.25
        }
        if isHovering {
            return 0.12
        }
        return 0
    }
}

// MARK: - IceBarItemClickView

private struct IceBarItemClickView: NSViewRepresentable {
    private final class Represented: NSView {
        let item: MenuBarItem

        let leftClickAction: () -> Void
        let rightClickAction: () -> Void

        @Binding var isHovering: Bool
        @Binding var isPressed: Bool

        private var trackingArea: NSTrackingArea?

        // A click only counts if it started on this view. Tracking the button
        // state explicitly keeps a stray mouse up — one whose mouse down landed
        // on a different item, or before this view existed — from firing an
        // action for the wrong item.
        private var isLeftMouseDownInside = false
        private var isRightMouseDownInside = false

        private var leftMouseDownLocation = CGPoint.zero
        private var rightMouseDownLocation = CGPoint.zero

        /// The distance the pointer may travel between mouse down and mouse up
        /// and still count as a click rather than a drag.
        private let dragThreshold: CGFloat = 10

        init(
            item: MenuBarItem,
            leftClickAction: @escaping () -> Void,
            rightClickAction: @escaping () -> Void,
            isHovering: Binding<Bool>,
            isPressed: Binding<Bool>
        ) {
            self.item = item
            self.leftClickAction = leftClickAction
            self.rightClickAction = rightClickAction
            self._isHovering = isHovering
            self._isPressed = isPressed
            super.init(frame: .zero)
            self.toolTip = item.displayName
        }

        @available(*, unavailable)
        required init?(coder: NSCoder) {
            fatalError("init(coder:) has not been implemented")
        }

        // The Ice Bar is a nonactivating panel, so SwiftUI's own hover tracking
        // is unreliable while another app is active. Track it here instead, with
        // `activeAlways`.
        override func updateTrackingAreas() {
            super.updateTrackingAreas()
            if let trackingArea {
                removeTrackingArea(trackingArea)
            }
            let trackingArea = NSTrackingArea(
                rect: .zero,
                options: [.mouseEnteredAndExited, .activeAlways, .inVisibleRect],
                owner: self
            )
            addTrackingArea(trackingArea)
            self.trackingArea = trackingArea
        }

        override func mouseEntered(with event: NSEvent) {
            super.mouseEntered(with: event)
            isHovering = true
        }

        override func mouseExited(with event: NSEvent) {
            super.mouseExited(with: event)
            isHovering = false
            isPressed = false
        }

        override func mouseDown(with event: NSEvent) {
            super.mouseDown(with: event)
            isLeftMouseDownInside = true
            leftMouseDownLocation = NSEvent.mouseLocation
            isPressed = true
        }

        override func rightMouseDown(with event: NSEvent) {
            super.rightMouseDown(with: event)
            isRightMouseDownInside = true
            rightMouseDownLocation = NSEvent.mouseLocation
            isPressed = true
        }

        override func mouseUp(with event: NSEvent) {
            super.mouseUp(with: event)
            isPressed = false
            guard isLeftMouseDownInside else {
                return
            }
            isLeftMouseDownInside = false
            // No time limit: a click that is held for a moment, or one that
            // lands while the window server is busy, is still a click. Only
            // pointer travel distinguishes a click from a drag.
            guard leftMouseDownLocation.distance(to: NSEvent.mouseLocation) < dragThreshold else {
                return
            }
            leftClickAction()
        }

        override func rightMouseUp(with event: NSEvent) {
            super.rightMouseUp(with: event)
            isPressed = false
            guard isRightMouseDownInside else {
                return
            }
            isRightMouseDownInside = false
            guard rightMouseDownLocation.distance(to: NSEvent.mouseLocation) < dragThreshold else {
                return
            }
            rightClickAction()
        }
    }

    let item: MenuBarItem

    let leftClickAction: () -> Void
    let rightClickAction: () -> Void

    @Binding var isHovering: Bool
    @Binding var isPressed: Bool

    func makeNSView(context: Context) -> NSView {
        Represented(
            item: item,
            leftClickAction: leftClickAction,
            rightClickAction: rightClickAction,
            isHovering: $isHovering,
            isPressed: $isPressed
        )
    }

    func updateNSView(_ nsView: NSView, context: Context) { }
}
