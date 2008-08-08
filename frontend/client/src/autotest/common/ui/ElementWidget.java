package autotest.common.ui;

import com.google.gwt.user.client.DOM;
import com.google.gwt.user.client.Element;
import com.google.gwt.user.client.ui.Widget;

/**
 * A simple widget that wraps an HTML element.  This allows the element to be
 * removed from the document and added to a Panel.
 */
public class ElementWidget extends Widget {
    protected Element element;

    /**
     * @param element the HTML element to wrap
     */
    public ElementWidget(Element element) {
        this.element = element;
        setElement(element);
        DOM.removeChild(DOM.getParent(element), element);
    }
    
    public ElementWidget(String elementId) {
        this(DOM.getElementById(elementId));
    }
}
