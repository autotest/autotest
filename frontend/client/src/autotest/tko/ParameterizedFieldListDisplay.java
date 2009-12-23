package autotest.tko;

import autotest.common.ui.ExtendedListBox;
import autotest.common.ui.SimpleHyperlink;
import autotest.common.ui.SimplifiedList;
import autotest.tko.ParameterizedFieldListPresenter.Display;

import com.google.gwt.event.dom.client.HasClickHandlers;
import com.google.gwt.user.client.ui.Composite;
import com.google.gwt.user.client.ui.HasText;
import com.google.gwt.user.client.ui.HorizontalPanel;
import com.google.gwt.user.client.ui.Label;
import com.google.gwt.user.client.ui.Panel;
import com.google.gwt.user.client.ui.TextBox;
import com.google.gwt.user.client.ui.VerticalPanel;
import com.google.gwt.user.client.ui.Widget;

public class ParameterizedFieldListDisplay extends Composite implements Display {
    private static class FieldWidget extends Composite implements Display.FieldWidget {
        private SimpleHyperlink deleteLink = new SimpleHyperlink("[X]");

        public FieldWidget(String label) {
            Panel panel = new HorizontalPanel();
            panel.add(new Label(label));
            panel.add(deleteLink);
            initWidget(panel);
        }

        @Override
        public HasClickHandlers getDeleteLink() {
            return deleteLink;
        }
    }
    
    private ExtendedListBox typeSelect = new ExtendedListBox();
    private TextBox valueInput = new TextBox();
    private SimpleHyperlink addLink = new SimpleHyperlink("Add");
    private Panel fieldListPanel = new VerticalPanel();
    
    public ParameterizedFieldListDisplay() {
        Panel addFieldPanel = new HorizontalPanel();
        addFieldPanel.add(new Label("Add custom field:"));
        addFieldPanel.add(typeSelect);
        addFieldPanel.add(valueInput);
        addFieldPanel.add(addLink);
        
        Panel container = new VerticalPanel();
        container.add(fieldListPanel);
        container.add(addFieldPanel);
        initWidget(container);
    }

    @Override
    public HasClickHandlers getAddLink() {
        return addLink;
    }

    @Override
    public SimplifiedList getTypeSelect() {
        return typeSelect;
    }

    @Override
    public HasText getValueInput() {
        return valueInput;
    }
    
    @Override
    public Display.FieldWidget addFieldWidget(String name) {
        FieldWidget widget = new FieldWidget(name);
        fieldListPanel.add(widget);
        return widget;
    }

    @Override
    public void removeFieldWidget(Display.FieldWidget widget) {
        fieldListPanel.remove((Widget) widget);
    }
}
