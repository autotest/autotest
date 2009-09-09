package autotest.common.ui;

import com.google.gwt.dom.client.Element;
import com.google.gwt.dom.client.EventTarget;
import com.google.gwt.event.dom.client.DoubleClickEvent;
import com.google.gwt.event.dom.client.DoubleClickHandler;
import com.google.gwt.event.dom.client.HasClickHandlers;
import com.google.gwt.event.shared.HandlerManager;
import com.google.gwt.event.shared.HandlerRegistration;
import com.google.gwt.user.client.ui.Button;
import com.google.gwt.user.client.ui.Composite;
import com.google.gwt.user.client.ui.HorizontalPanel;
import com.google.gwt.user.client.ui.Panel;
import com.google.gwt.user.client.ui.VerticalPanel;

public class DoubleListSelector extends Composite 
                                implements MultiListSelectPresenter.DoubleListDisplay,
                                           DoubleClickHandler {
    private static final int VISIBLE_ITEMS = 10;

    private Panel container = new HorizontalPanel();
    private ExtendedListBox availableBox = new ExtendedListBox();
    private ExtendedListBox selectedBox = new ExtendedListBox();
    private Button addButton = new Button("Add >"), addAllButton = new Button("Add all >");
    private Button removeButton = new Button("< Remove"), 
                   removeAllButton = new Button("< Remove all");
    private Button moveUpButton = new Button("Move up"), moveDownButton = new Button("Move down");

    private HandlerManager availableListHandlerManager = new HandlerManager(availableBox);
    private HandlerManager selectedListHandlerManager = new HandlerManager(selectedBox);

    public DoubleListSelector() {
        availableBox.setVisibleItemCount(VISIBLE_ITEMS);
        selectedBox.setVisibleItemCount(VISIBLE_ITEMS);

        Panel moveButtonPanel = new VerticalPanel();
        moveButtonPanel.add(addAllButton);
        moveButtonPanel.add(addButton);
        moveButtonPanel.add(removeButton);
        moveButtonPanel.add(removeAllButton);

        Panel reorderButtonPanel = new VerticalPanel();
        reorderButtonPanel.add(moveUpButton);
        reorderButtonPanel.add(moveDownButton);

        container.add(availableBox);
        container.add(moveButtonPanel);
        container.add(selectedBox);
        container.add(reorderButtonPanel);

        initWidget(container);
        
        addDomHandler(this, DoubleClickEvent.getType());
    }

    public HasClickHandlers getAddAllButton() {
        return addAllButton;
    }

    public HasClickHandlers getAddButton() {
        return addButton;
    }

    public HasClickHandlers getRemoveButton() {
        return removeButton;
    }

    public HasClickHandlers getRemoveAllButton() {
        return removeAllButton;
    }

    public HasClickHandlers getMoveUpButton() {
        return moveUpButton;
    }

    public HasClickHandlers getMoveDownButton() {
        return moveDownButton;
    }

    public SimplifiedList getAvailableList() {
        return availableBox;
    }

    public SimplifiedList getSelectedList() {
        return selectedBox;
    }

    @Override
    public HandlerRegistration addDoubleClickHandler(DoubleClickHandler handler) {
        availableListHandlerManager.addHandler(DoubleClickEvent.getType(), handler);
        selectedListHandlerManager.addHandler(DoubleClickEvent.getType(), handler);
        // removing handlers is unimplemented for now.  if the need arises, it's easy to implement.
        return null;
    }

    @Override
    public void onDoubleClick(DoubleClickEvent event) {
        EventTarget target = event.getNativeEvent().getEventTarget();
        Element targetElement = Element.as(target);
        if (availableBox.getElement().isOrHasChild(targetElement)) {
            availableListHandlerManager.fireEvent(event);
        } else if (selectedBox.getElement().isOrHasChild(targetElement)) {
            selectedListHandlerManager.fireEvent(event);
        } else {
            return;
        }
        
        event.stopPropagation();
    }
}
