// Copyright 2008 Google Inc. All Rights Reserved.

package autotest.common.table;


import com.google.gwt.user.client.ui.CheckBox;
import com.google.gwt.user.client.ui.ClickListener;
import com.google.gwt.user.client.ui.Widget;

public abstract class CheckboxFilter extends FieldFilter implements ClickListener {
    private CheckBox checkBox = new CheckBox();
    
    public CheckboxFilter(String fieldName) {
        super(fieldName);
        checkBox.addClickListener(this);
    }
    
    public void onClick(Widget sender) {
        notifyListeners();
    }

    @Override
    public Widget getWidget() {
        return checkBox;
    }

    @Override
    public boolean isActive() {
        return checkBox.isChecked();
    }
    
    public void setActive(boolean active) {
        checkBox.setChecked(active);
    }
}