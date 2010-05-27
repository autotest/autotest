// Copyright 2008 Google Inc. All Rights Reserved.

package autotest.common.table;


import com.google.gwt.event.dom.client.ClickEvent;
import com.google.gwt.event.dom.client.ClickHandler;
import com.google.gwt.user.client.ui.CheckBox;
import com.google.gwt.user.client.ui.Widget;

public abstract class CheckboxFilter extends FieldFilter implements ClickHandler {
    private CheckBox checkBox = new CheckBox();

    public CheckboxFilter(String fieldName) {
        super(fieldName);
        checkBox.addClickHandler(this);
    }

    public void onClick(ClickEvent event) {
        notifyListeners();
    }

    @Override
    public Widget getWidget() {
        return checkBox;
    }

    @Override
    public boolean isActive() {
        return checkBox.getValue();
    }

    public void setActive(boolean active) {
        checkBox.setValue(active);
    }
}
